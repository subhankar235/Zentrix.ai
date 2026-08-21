"""Deterministic Policy Engine for guarded optimization deployment.

Evaluates simulation and verification results against hard, non-overridable
safety and performance thresholds before canary deployment or user approval.

Independent of LLM judgments per ARCHITECTURE.md §4, §8 & PRD.md §5 Feature 2.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class PolicyConfig:
    """Configurable threshold parameters for deterministic deployment gating."""

    min_p95_improvement_ratio: float = 0.10  # >= 10% p95 latency reduction
    require_ci_excludes_zero: bool = True  # CI upper bound must be < 0
    max_regression_rate: float = 0.05  # <= 5% of workload queries regressed
    max_write_latency_increase_ratio: float = 0.15  # <= 15% write latency increase
    max_storage_increase_ratio: float = 0.20  # <= 20% storage/index growth
    max_skeptic_score: float = 0.40  # Skeptic adversarial risk score < 0.40
    min_sample_size: int = 10  # Minimum paired workload observations


def _number(mapping: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        val = mapping.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue
    return default


def evaluate(
    verification_result: Mapping[str, Any],
    config: PolicyConfig | None = None,
) -> dict[str, Any]:
    """Evaluate simulation/verification metrics against deterministic safety rules.

    Returns a structured PolicyVerdict dict with APPROVE, BLOCK, or CONDITIONAL.
    """
    cfg = config or PolicyConfig()
    passed_rules: list[str] = []
    violated_rules: list[str] = []

    # 1. Sample Size / Statistical Power Check
    sample_size = int(_number(verification_result, "sample_size", "paired_samples", default=0))
    is_underpowered = sample_size > 0 and sample_size < cfg.min_sample_size
    if is_underpowered:
        violated_rules.append(
            f"Sample size ({sample_size}) is below minimum required ({cfg.min_sample_size})"
        )
    else:
        passed_rules.append("statistical_sample_size")

    # 2. P95 Latency Improvement Check
    baseline_p95 = _number(verification_result, "baseline_p95", "p95_baseline")
    candidate_p95 = _number(verification_result, "candidate_p95", "p95_candidate")
    p95_improvement = _number(
        verification_result,
        "p95_improvement_ratio",
        "p95_improvement",
        default=(
            (baseline_p95 - candidate_p95) / max(baseline_p95, 1e-6)
            if baseline_p95 > 0
            else 0.0
        ),
    )
    if p95_improvement < cfg.min_p95_improvement_ratio:
        violated_rules.append(
            f"p95 improvement ({p95_improvement:.1%}) below required threshold ({cfg.min_p95_improvement_ratio:.1%})"
        )
    else:
        passed_rules.append("p95_improvement")

    # 3. Bootstrap Confidence Interval Check (excludes zero / upper < 0)
    ci_upper = _number(verification_result, "ci_upper", "ci_high", "ci_95_upper", default=0.0)
    ci_excludes_zero = verification_result.get("ci_excludes_zero")
    if ci_excludes_zero is None:
        ci_excludes_zero = ci_upper < 0.0 or (p95_improvement >= cfg.min_p95_improvement_ratio and sample_size >= cfg.min_sample_size)
    if cfg.require_ci_excludes_zero and not bool(ci_excludes_zero):
        violated_rules.append("Bootstrap confidence interval does not exclude zero")
    else:
        passed_rules.append("confidence_interval_excludes_zero")

    # 4. Query Regression Rate Check
    regression_rate = _number(verification_result, "regression_rate", default=0.0)
    if regression_rate > cfg.max_regression_rate:
        violated_rules.append(
            f"Workload regression rate ({regression_rate:.1%}) exceeds threshold ({cfg.max_regression_rate:.1%})"
        )
    else:
        passed_rules.append("regression_rate")

    # 5. Write Latency / DML Degradation Check
    write_increase = _number(
        verification_result,
        "write_latency_increase_ratio",
        "write_latency_delta",
        "write_amplification",
        default=0.0,
    )
    if write_increase > cfg.max_write_latency_increase_ratio:
        violated_rules.append(
            f"Write latency increase ({write_increase:.1%}) exceeds threshold ({cfg.max_write_latency_increase_ratio:.1%})"
        )
    else:
        passed_rules.append("write_latency_overhead")

    # 6. Storage Growth Check
    storage_increase = _number(
        verification_result,
        "storage_increase_ratio",
        "storage_delta",
        "index_size_ratio",
        default=0.0,
    )
    if storage_increase > cfg.max_storage_increase_ratio:
        violated_rules.append(
            f"Storage growth ({storage_increase:.1%}) exceeds threshold ({cfg.max_storage_increase_ratio:.1%})"
        )
    else:
        passed_rules.append("storage_growth")

    # 7. Skeptic Agent Adversarial Risk Score Check
    skeptic_score = _number(
        verification_result,
        "skeptic_score",
        "skeptic_risk_score",
        "risk_score",
        default=0.0,
    )
    if skeptic_score > cfg.max_skeptic_score:
        violated_rules.append(
            f"Skeptic adversarial risk score ({skeptic_score:.2f}) exceeds allowed maximum ({cfg.max_skeptic_score:.2f})"
        )
    else:
        passed_rules.append("skeptic_risk_assessment")

    # Final Verdict Synthesis
    if not violated_rules:
        verdict = "APPROVE"
        status = "VERIFIED"
    elif is_underpowered and len(violated_rules) == 1:
        # Only underpowered, otherwise passed all metric thresholds
        verdict = "CONDITIONAL"
        status = "CONDITIONAL"
    else:
        verdict = "BLOCK"
        status = "REJECTED"

    return {
        "verdict": verdict,
        "status": status,
        "canary_eligible": verdict == "APPROVE",
        "passed_rules": passed_rules,
        "violated_rules": violated_rules,
        "metrics_summary": {
            "sample_size": sample_size,
            "p95_improvement_ratio": p95_improvement,
            "ci_excludes_zero": bool(ci_excludes_zero),
            "regression_rate": regression_rate,
            "write_latency_increase_ratio": write_increase,
            "storage_increase_ratio": storage_increase,
            "skeptic_score": skeptic_score,
        },
        "policy_config": asdict(cfg),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }

