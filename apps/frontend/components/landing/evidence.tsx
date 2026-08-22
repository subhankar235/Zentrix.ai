"use client";

import { motion } from "framer-motion";
import { Database, Cpu, Network, FlaskConical, Rocket } from "lucide-react";
import { SectionHeading } from "./section-heading";

const stages = [
  {
    icon: Database,
    tag: "01 · collect",
    title: "Read-only telemetry",
    body: "A collector polls pg_stat_statements, pg_stat_activity, pg_locks, vacuum progress and buffer/IO stats every 1–5 minutes into normalized evidence tables.",
  },
  {
    icon: Cpu,
    tag: "02 · detect",
    title: "ML anomaly layer",
    body: "Isolation Forest on point features, an LSTM autoencoder on temporal shape, and a LightGBM RCA classifier score what actually broke — not what merely spiked.",
  },
  {
    icon: Network,
    tag: "03 · diagnose",
    title: "Multi-agent causality",
    body: "Five specialists each read their own slice of evidence through typed tools. A supervisor reconciles conflicting hypotheses into one causal report with a validation plan.",
  },
  {
    icon: FlaskConical,
    tag: "04 · verify",
    title: "Simulate, then prove",
    body: "HypoPG hypothetical indexes plus a shadow clone replay. Paired statistical testing decides VERIFIED, CONDITIONAL or REJECTED before anyone sees a suggestion.",
  },
  {
    icon: Rocket,
    tag: "05 · deploy",
    title: "Guarded canary",
    body: "Only CREATE INDEX CONCURRENTLY and ANALYZE, only after policy-engine approval and a human click, watched by a canary monitor that rolls back on breach.",
  },
];

export function Evidence() {
  return (
    <section id="evidence" className="relative border-t border-border py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-5">
        <SectionHeading
          label="pipeline"
          title="Evidence in. Verdict out."
          desc="Every number on screen is computed deterministically. The language model interprets — it never invents a metric, and never writes SQL against your database."
        />

        <div className="mt-14 grid gap-px overflow-hidden rounded-xl border border-border bg-border md:grid-cols-3">
          {stages.map((s, i) => (
            <motion.article
              key={s.tag}
              initial={{ opacity: 0, y: 22 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.55, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] }}
              className={`group relative overflow-hidden bg-surface p-7 transition-colors hover:bg-surface-2 ${
                i >= 3 ? "md:col-span-1 lg:col-span-1" : ""
              }`}
            >
              <div className="absolute inset-x-0 top-0 h-px scale-x-0 bg-signal transition-transform duration-500 group-hover:scale-x-100" />
              <s.icon className="h-5 w-5 text-signal" strokeWidth={1.6} />
              <p className="mono-label mt-5 text-muted-foreground">{s.tag}</p>
              <h3 className="mt-2 font-display text-lg font-semibold tracking-tight">{s.title}</h3>
              <p className="mt-3 text-[13.5px] leading-relaxed text-muted-foreground">{s.body}</p>
            </motion.article>
          ))}
          <div className="hidden bg-surface md:block" />
        </div>
      </div>
    </section>
  );
}
