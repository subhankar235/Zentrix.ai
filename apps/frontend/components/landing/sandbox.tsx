"use client";

import { motion } from "framer-motion";
import { SectionHeading } from "./section-heading";

const steps = [
  { t: "clone", d: "pg_dump → ephemeral shadow container", state: "done" },
  { t: "hypopg", d: "hypothetical index, session-local, never persisted", state: "done" },
  { t: "replay", d: "paired workload replay, 40 iterations", state: "done" },
  { t: "skeptic", d: "2 regression probes · 0 red flags", state: "warn" },
  { t: "verdict", d: "VERIFIED · p = 0.003 · Δ p95 −71%", state: "ok" },
  { t: "canary", d: "awaiting human approval", state: "idle" },
];

const dotColor: Record<string, string> = {
  done: "bg-muted-foreground",
  warn: "bg-warn",
  ok: "bg-verified",
  idle: "bg-signal",
};

export function Sandbox() {
  return (
    <section id="sandbox" className="relative border-t border-border py-24 md:py-32">
      <div className="pointer-events-none absolute right-0 top-1/3 h-72 w-72 rounded-full bg-verified/10 blur-[110px]" />
      <div className="relative mx-auto grid max-w-6xl gap-14 px-5 lg:grid-cols-2 lg:items-center">
        <div>
          <SectionHeading
            label="feature 02 · sandbox"
            title="No unproven change ever reaches production."
            desc="Candidates are generated deterministically — never free-form LLM SQL. They are simulated in a shadow clone, statistically tested against the baseline, attacked by a skeptic agent, and gated by a rule engine with no model in the loop."
          />
          <ul className="mt-8 space-y-3 text-[14px] text-muted-foreground">
            {[
              "HypoPG hypothetical indexes inside a rolled-back transaction",
              "Ephemeral Docker Postgres clones, destroyed on completion",
              "Paired statistical testing before a verdict is issued",
              "Only CREATE INDEX CONCURRENTLY and ANALYZE ever run for real",
            ].map((li) => (
              <li key={li} className="flex gap-3">
                <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-signal" />
                {li}
              </li>
            ))}
          </ul>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 26 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="relative overflow-hidden rounded-xl border border-border bg-surface shadow-instrument"
        >
          <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-signal/12 to-transparent [animation:scan-sweep_6s_linear_infinite]" />
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="mono-label text-muted-foreground">experiment · exp_10c4</span>
            <span className="flex items-center gap-2 font-mono text-[10.5px] text-verified">
              <span className="h-1.5 w-1.5 rounded-full bg-verified [animation:pulse-node_1.8s_ease-in-out_infinite]" />
              live
            </span>
          </div>

          <ol className="relative px-5 py-5">
            <span className="absolute left-[26px] top-8 bottom-8 w-px bg-border" />
            {steps.map((s, i) => (
              <motion.li
                key={s.t}
                initial={{ opacity: 0, x: -10 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.15 + i * 0.12, duration: 0.45 }}
                className="relative flex gap-4 py-2.5 pl-1"
              >
                <span
                  className={`relative z-10 mt-1.5 h-2 w-2 shrink-0 rounded-full ring-4 ring-surface ${dotColor[s.state]}`}
                />
                <div>
                  <p className="font-mono text-[12px] text-foreground">{s.t}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">{s.d}</p>
                </div>
              </motion.li>
            ))}
          </ol>

          <div className="grid grid-cols-3 gap-px border-t border-border bg-border">
            {[
              { k: "baseline p95", v: "412 ms" },
              { k: "candidate p95", v: "119 ms" },
              { k: "regressions", v: "0" },
            ].map((m) => (
              <div key={m.k} className="bg-surface px-4 py-4">
                <p className="mono-label text-muted-foreground">{m.k}</p>
                <p className="mt-1 font-display text-lg font-semibold tracking-tight">{m.v}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
