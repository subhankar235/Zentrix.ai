"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SectionHeading } from "./section-heading";

type Agent = {
  name: string;
  role: string;
  tools: string;
  model: string;
  output: string;
};

const graphs: Record<string, { blurb: string; agents: Agent[] }> = {
  Diagnosis: {
    blurb: "graph_diagnosis.py — five specialists, one supervisor, zero shared memory.",
    agents: [
      {
        name: "Planner Intelligence",
        role: "Plan regression, cardinality error, statistics freshness",
        tools: "get_explain_plan · get_pg_stats · compare_plan",
        model: "RCA classifier (LightGBM)",
        output: "Hypothesis + confidence",
      },
      {
        name: "Concurrency",
        role: "Lock chains, blocking sessions, idle-in-transaction",
        tools: "get_pg_activity · get_pg_locks",
        model: "—",
        output: "Hypothesis + confidence",
      },
      {
        name: "Vacuum",
        role: "Dead-tuple ratio, bloat, autovacuum lag",
        tools: "get_vacuum_progress",
        model: "—",
        output: "Hypothesis + confidence",
      },
      {
        name: "I/O · Buffer",
        role: "Cache eviction, temp spill, WAL pressure",
        tools: "get_buffer_stats · get_io_stats",
        model: "—",
        output: "Hypothesis + confidence",
      },
      {
        name: "Schema · Index",
        role: "Missing, unused and redundant indexes",
        tools: "get_indexes · get_index_usage",
        model: "—",
        output: "Hypothesis + confidence",
      },
      {
        name: "Supervisor",
        role: "Reconciles every specialist into one causal report",
        tools: "—",
        model: "—",
        output: "Root-cause report + validation plan",
      },
    ],
  },
  Simulation: {
    blurb: "graph_simulation.py — nothing reaches production without a verdict.",
    agents: [
      {
        name: "Experiment",
        role: "Runs the shadow experiment against a cloned database",
        tools: "shadow_db_tool · hypopg_tool",
        model: "—",
        output: "Baseline / candidate metrics",
      },
      {
        name: "ML Scientist",
        role: "Reads the delta prediction, asks for more samples when unsure",
        tools: "—",
        model: "Delta Predictor (LightGBM)",
        output: "Confidence assessment",
      },
      {
        name: "Skeptic",
        role: "Actively hunts for regressions the happy path would miss",
        tools: "pg_introspection (regression queries)",
        model: "—",
        output: "List of red flags",
      },
      {
        name: "Verification",
        role: "Fuses statistics, model output and skeptic findings",
        tools: "—",
        model: "—",
        output: "VERIFIED / CONDITIONAL / REJECTED",
      },
      {
        name: "Policy",
        role: "Deterministic go / no-go rules — no LLM involved",
        tools: "policy_engine.py",
        model: "—",
        output: "Approve or block canary",
      },
      {
        name: "Deployment",
        role: "Executes the approved change, watches canary, rolls back",
        tools: "guarded write path",
        model: "—",
        output: "Deployment result",
      },
    ],
  },
  Forecast: {
    blurb: "graph_forecast.py — the loop that makes tomorrow's prediction sharper.",
    agents: [
      {
        name: "Forecasting · Planning",
        role: "Decides whether predicted degradation warrants acting now",
        tools: "—",
        model: "LightGBM + conformal, Thompson bandit",
        output: "Triggers a simulation run",
      },
      {
        name: "Learning",
        role: "Logs real outcome vs. prediction, promotes better models",
        tools: "—",
        model: "MLflow registry",
        output: "Updated model version",
      },
    ],
  },
};

const tabs = Object.keys(graphs);

export function Agents() {
  const [active, setActive] = useState(tabs[0]!);
  const graph = graphs[active]!;

  return (
    <section id="agents" className="relative border-t border-border py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-5">
        <SectionHeading
          label="agent architecture"
          title="Specialists, not a chatbot."
          desc="Each agent sees only its own evidence and calls only its own typed Python tools. None of them ever receives database credentials or an open SQL prompt."
        />

        <div className="mt-10 inline-flex rounded-md border border-border bg-surface p-1">
          {tabs.map((t) => (
            <button
              key={t}
              onClick={() => setActive(t)}
              className="relative rounded-[5px] px-4 py-2 font-mono text-xs transition-colors"
            >
              {active === t && (
                <motion.span
                  layoutId="agent-tab"
                  className="absolute inset-0 rounded-[5px] bg-primary"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <span
                className={`relative z-10 ${active === t ? "text-primary-foreground" : "text-muted-foreground"}`}
              >
                {t}
              </span>
            </button>
          ))}
        </div>

        <p className="mt-4 font-mono text-xs text-muted-foreground">{graph.blurb}</p>

        <AnimatePresence mode="wait">
          <motion.div
            key={active}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3"
          >
            {graph.agents.map((a, i) => (
              <motion.div
                key={a.name}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05, duration: 0.4 }}
                className="group relative overflow-hidden rounded-lg border border-border bg-surface p-5 transition-all hover:-translate-y-1 hover:border-signal/45 hover:shadow-instrument"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-display text-[15px] font-semibold tracking-tight">{a.name}</h3>
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-signal [animation:pulse-node_2.6s_ease-in-out_infinite]" />
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{a.role}</p>
                <dl className="mt-4 space-y-1.5 border-t border-border pt-3 font-mono text-[10.5px] text-muted-foreground">
                  <div className="flex gap-2">
                    <dt className="w-12 shrink-0 text-signal">tools</dt>
                    <dd className="break-words">{a.tools}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-12 shrink-0 text-signal">model</dt>
                    <dd>{a.model}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-12 shrink-0 text-signal">out</dt>
                    <dd className="text-foreground">{a.output}</dd>
                  </div>
                </dl>
              </motion.div>
            ))}
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  );
}
