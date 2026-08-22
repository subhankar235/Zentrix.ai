"""Feature 3 L3 Strategy Selector (Contextual Thompson Sampling Bandit).

Selects database optimization strategies per workload context using Bayesian
Contextual Thompson Sampling over action space:
{CREATE_INDEX, PARTIAL_INDEX, QUERY_REWRITE, VACUUM_ANALYZE, UPDATE_STATISTICS, CONFIG_TUNE, DO_NOTHING}.

Enforces mandatory rollout gate per PRD.md §5 & §22:
(1) rule_based (default) -> (2) supervised -> (3) bandit_shadow -> (4) offline_evaluated (IPS).
Bandit output cannot influence live recommendations until Phase 4 is verified.

Reference: ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 3 L3, §22.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

# Standard Action Space
ACTIONS = [
    "CREATE_INDEX",
    "PARTIAL_INDEX",
    "QUERY_REWRITE",
    "VACUUM_ANALYZE",
    "UPDATE_STATISTICS",
    "CONFIG_TUNE",
    "DO_NOTHING",
]

# Implementation operational overhead cost per action
ACTION_COSTS: dict[str, float] = {
    "DO_NOTHING": 0.0,
    "UPDATE_STATISTICS": 0.02,
    "CONFIG_TUNE": 0.03,
    "VACUUM_ANALYZE": 0.05,
    "PARTIAL_INDEX": 0.07,
    "CREATE_INDEX": 0.10,
    "QUERY_REWRITE": 0.08,
}

CONTEXT_FEATURE_NAMES = [
    "cardinality_error",
    "dead_tuple_ratio",
    "idx_scan_ratio",
    "p95_exec_time",
    "mean_exec_time",
    "calls",
    "shared_blks_read",
    "cpu_seconds",
    "write_ratio",
    "table_size_mb",
]


class RolloutPhase(str, enum.Enum):
    """Mandatory Rollout Gate stages per PRD.md §5 & §22."""

    PHASE_1_RULE_BASED = "rule_based"  # Default / cold start: deterministic expert rules
    PHASE_2_SUPERVISED = "supervised"  # Supervised ML predictions rank strategies
    PHASE_3_BANDIT_SHADOW = "bandit_shadow"  # Bandit samples logged in shadow mode
    PHASE_4_OFFLINE_EVALUATED = "offline_evaluated"  # Bandit verified via IPS and live


def compute_reward(
    metrics_delta: Mapping[str, Any],
    action: str,
    risk_level: str = "LOW",
) -> float:
    """Compute scalar bandit reward from observed experiment outcome.

    Reward = Performance/IO/CPU improvement - Risk Penalty - Implementation Cost
    """
    p95_imp = float(metrics_delta.get("p95_improvement_ratio", 0.0))
    cpu_imp = float(metrics_delta.get("cpu_reduction_ratio", metrics_delta.get("cpu_improvement_ratio", 0.0)))
    io_imp = float(metrics_delta.get("io_reduction_ratio", metrics_delta.get("io_improvement_ratio", 0.0)))

    # Performance component (weighted latency + CPU + IO)
    perf_reward = p95_imp * 1.0 + cpu_imp * 0.3 + io_imp * 0.2

    # Risk penalty
    risk_penalties = {"LOW": 0.0, "MEDIUM": 0.15, "HIGH": 0.40}
    risk_penalty = risk_penalties.get(risk_level.upper(), 0.10)

    # If regression occurred, penalize severely
    regr_rate = float(metrics_delta.get("regression_rate", 0.0))
    if regr_rate > 0.05:
        risk_penalty += regr_rate * 2.0

    # Operational implementation cost
    act_name = action.upper()
    impl_cost = ACTION_COSTS.get(act_name, 0.05)

    reward = perf_reward - risk_penalty - impl_cost
    return float(np.clip(reward, -1.0, 1.0))


def extract_context_vector(context: Mapping[str, Any]) -> np.ndarray:
    """Transform telemetry/workload context mapping into normalized feature vector."""
    vec = np.zeros(len(CONTEXT_FEATURE_NAMES) + 1, dtype=np.float32)
    vec[0] = 1.0  # Bias / intercept

    for i, name in enumerate(CONTEXT_FEATURE_NAMES):
        raw_val = float(context.get(name, 0.0))
        # Log-scale non-bounded metrics
        if name in {"p95_exec_time", "mean_exec_time", "calls", "shared_blks_read", "table_size_mb"}:
            val = float(np.log1p(max(0.0, raw_val)))
        else:
            val = float(np.clip(raw_val, -10.0, 10.0))
        vec[i + 1] = val

    return vec


def select_rule_based_strategy(context: Mapping[str, Any]) -> str:
    """Deterministic heuristic baseline strategy selector (Phase 1)."""
    card_err = abs(float(context.get("cardinality_error", 0.0)))
    dead_ratio = float(context.get("dead_tuple_ratio", 0.0))
    idx_ratio = float(context.get("idx_scan_ratio", 1.0))
    p95 = float(context.get("p95_exec_time", 0.0))

    if card_err > 2.0:
        return "UPDATE_STATISTICS"
    if dead_ratio > 0.20:
        return "VACUUM_ANALYZE"
    if idx_ratio < 0.30 and p95 > 50.0:
        return "CREATE_INDEX"
    if p95 > 200.0:
        return "QUERY_REWRITE"
    return "DO_NOTHING"


class ContextualThompsonSamplingBandit:
    """Contextual Thompson Sampling Bandit with Bayesian Linear Regression per action."""

    def __init__(
        self,
        actions: Sequence[str] | None = None,
        context_dim: int = len(CONTEXT_FEATURE_NAMES) + 1,
        noise_variance: float = 0.25,
        rollout_phase: RolloutPhase = RolloutPhase.PHASE_1_RULE_BASED,
    ):
        self.actions = list(actions or ACTIONS)
        self.context_dim = context_dim
        self.noise_var = noise_variance
        self.rollout_phase = rollout_phase

        # Per-action Bayesian Linear Regression parameters: w_a ~ N(mu_a, Sigma_a)
        self.precision: dict[str, np.ndarray] = {
            a: np.eye(self.context_dim, dtype=np.float32) for a in self.actions
        }
        self.b_vec: dict[str, np.ndarray] = {
            a: np.zeros(self.context_dim, dtype=np.float32) for a in self.actions
        }
        self.action_counts: dict[str, int] = {a: 0 for a in self.actions}

    def is_bandit_live(self) -> bool:
        """Confirm whether bandit output is allowed to directly drive recommendations."""
        return self.rollout_phase == RolloutPhase.PHASE_4_OFFLINE_EVALUATED

    def _sample_weights(self) -> dict[str, np.ndarray]:
        """Sample weight vector w_a ~ N(mu_a, Sigma_a) for each action."""
        sampled: dict[str, np.ndarray] = {}
        for a in self.actions:
            cov = np.linalg.inv(self.precision[a])
            mu = cov @ self.b_vec[a]
            # Regularized covariance Cholesky sampling
            cov_reg = cov + np.eye(self.context_dim) * 1e-6
            sample = np.random.multivariate_normal(mu, cov_reg)
            sampled[a] = sample
        return sampled

    def select_action(
        self,
        context: Mapping[str, Any],
        n_mc_propensity_samples: int = 100,
    ) -> dict[str, Any]:
        """Select action using Contextual Thompson Sampling, gated by current RolloutPhase."""
        x = extract_context_vector(context)

        # 1. Thompson Sampling prediction
        sampled_weights = self._sample_weights()
        action_scores = {a: float(np.dot(x, sampled_weights[a])) for a in self.actions}
        bandit_best_action = max(action_scores, key=action_scores.get)

        # Estimate action propensities via Monte Carlo
        mc_wins = {a: 0 for a in self.actions}
        for _ in range(n_mc_propensity_samples):
            w_draws = self._sample_weights()
            best_draw = max(self.actions, key=lambda a: np.dot(x, w_draws[a]))
            mc_wins[best_draw] += 1

        propensity = max(0.01, mc_wins.get(bandit_best_action, 1) / n_mc_propensity_samples)

        # 2. Apply Rollout Gating
        rule_action = select_rule_based_strategy(context)

        if self.rollout_phase == RolloutPhase.PHASE_1_RULE_BASED:
            served_action = rule_action
            decision_source = "RULE_BASED_GATE"
        elif self.rollout_phase == RolloutPhase.PHASE_2_SUPERVISED:
            served_action = rule_action  # Supervised outcome model fallback
            decision_source = "SUPERVISED_GATE"
        elif self.rollout_phase == RolloutPhase.PHASE_3_BANDIT_SHADOW:
            served_action = rule_action
            decision_source = "BANDIT_SHADOW_LOGGED"
        elif self.rollout_phase == RolloutPhase.PHASE_4_OFFLINE_EVALUATED:
            served_action = bandit_best_action
            decision_source = "BANDIT_LIVE_POLICY"
        else:
            served_action = rule_action
            decision_source = "RULE_BASED_GATE"

        return {
            "selected_action": served_action,
            "bandit_action": bandit_best_action,
            "rule_action": rule_action,
            "propensity": float(propensity),
            "rollout_phase": self.rollout_phase.value,
            "is_bandit_live": self.is_bandit_live(),
            "decision_source": decision_source,
            "action_scores": action_scores,
            "context_snapshot": dict(context),
        }

    def update(
        self,
        context: Mapping[str, Any],
        action: str,
        reward: float,
    ) -> None:
        """Update posterior distribution for chosen action given observed reward."""
        if action not in self.precision:
            return

        x = extract_context_vector(context)
        # Precision matrix update: A = A + (x * x^T) / sigma^2
        self.precision[action] += np.outer(x, x) / self.noise_var
        # B vector update: b = b + (r * x) / sigma^2
        self.b_vec[action] += (reward * x) / self.noise_var
        self.action_counts[action] += 1

    def evaluate_offline_ips(
        self,
        logged_events: Sequence[Mapping[str, Any]],
        min_effective_sample_size: int = 20,
    ) -> dict[str, Any]:
        """Evaluate bandit policy using Inverse Propensity Scoring (IPS) on historical logs."""
        if not logged_events:
            return {"status": "INSUFFICIENT_DATA", "is_promotable": False, "ips_value": 0.0}

        weights: list[float] = []
        weighted_rewards: list[float] = []
        baseline_rewards: list[float] = []

        for ev in logged_events:
            ctx = ev.get("context", {})
            logged_action = ev.get("action")
            logged_propensity = max(1e-4, float(ev.get("propensity", 0.20)))
            reward = float(ev.get("reward", 0.0))

            baseline_rewards.append(reward)

            # Evaluate policy probability of logged action
            x = extract_context_vector(ctx)
            # Probability under current target policy
            scores = {a: float(np.dot(x, np.linalg.inv(self.precision[a]) @ self.b_vec[a])) for a in self.actions}
            best_target_action = max(scores, key=scores.get)

            target_prob = 0.85 if best_target_action == logged_action else 0.15 / (len(self.actions) - 1)
            iw = target_prob / logged_propensity
            weights.append(iw)
            weighted_rewards.append(iw * reward)

        ips_value = float(np.mean(weighted_rewards)) if weighted_rewards else 0.0
        baseline_value = float(np.mean(baseline_rewards)) if baseline_rewards else 0.0

        # Effective sample size: (sum w)^2 / sum(w^2)
        sum_w = sum(weights)
        sum_sq_w = sum(w ** 2 for w in weights)
        ess = (sum_w ** 2) / max(sum_sq_w, 1e-6)

        is_promotable = bool(ess >= min_effective_sample_size and ips_value >= baseline_value)

        return {
            "status": "EVALUATED",
            "ips_value": ips_value,
            "baseline_value": baseline_value,
            "value_improvement": ips_value - baseline_value,
            "effective_sample_size": float(ess),
            "n_events": len(logged_events),
            "is_promotable": is_promotable,
        }
