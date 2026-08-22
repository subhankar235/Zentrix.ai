"use client";

import { useRef, type ReactNode } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function SectionHead({
  label,
  title,
  body,
}: {
  label: string;
  title: string;
  body?: string;
}) {
  return (
    <Reveal className="max-w-2xl">
      <p className="mono-label text-muted-foreground">{label}</p>
      <h2 className="mt-3 text-[1.6rem] leading-[1.15] font-semibold tracking-[-0.025em] text-balance sm:text-[2.1rem]">
        {title}
      </h2>
      {body ? (
        <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">{body}</p>
      ) : null}
    </Reveal>
  );
}

const steps = [
  {
    k: "Collect",
    d: "A read-only collector polls pg_stat_statements, pg_stat_activity, pg_locks, vacuum and I/O stats every 1–5 minutes.",
    m: "asyncpg · read-only",
  },
  {
    k: "Detect",
    d: "Isolation Forest and a temporal autoencoder flag anomalies against the workload's own history, not generic thresholds.",
    m: "ml/anomaly · ml/temporal",
  },
  {
    k: "Diagnose",
    d: "Specialist agents build hypotheses from evidence; the supervisor reconciles them into one causal report.",
    m: "graph_diagnosis",
  },
  {
    k: "Simulate",
    d: "Candidates run against HypoPG and an ephemeral shadow clone; results are tested for statistical significance.",
    m: "shadow_db · hypopg",
  },
  {
    k: "Approve",
    d: "A deterministic policy engine gates the change, and a human signs off. No approval, no production write.",
    m: "policy_engine",
  },
  {
    k: "Deploy & learn",
    d: "CREATE INDEX CONCURRENTLY under canary watch with auto-rollback; the real outcome retrains the models.",
    m: "canary_monitor · MLflow",
  },
];

export function Pipeline() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 75%", "end 60%"],
  });
  const height = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);

  return (
    <section id="pipeline" className="border-t border-border bg-surface/50">
      <div className="mx-auto max-w-[1180px] px-5 py-20 md:px-8 md:py-28">
        <SectionHead
          label="How it works"
          title="One guarded path from telemetry to a verified production change."
          body="Agents never hold credentials and never write free-form SQL. Every step below is a separate, auditable stage backed by a row in the system's own database."
        />

        <div ref={ref} className="relative mt-14 pl-8 md:pl-0">
          <div className="absolute top-0 bottom-0 left-[7px] w-px bg-border md:left-1/2" />
          <motion.div
            style={{ height }}
            className="absolute top-0 left-[7px] w-px origin-top bg-signal md:left-1/2"
          />

          {steps.map((s, i) => (
            <motion.div
              key={s.k}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
              className="relative pb-12 last:pb-0 md:grid md:grid-cols-2 md:gap-16"
            >
              <span className="absolute top-1.5 -left-8 h-[15px] w-[15px] rounded-full border border-border bg-background md:left-1/2 md:-ml-[7.5px]">
                <span className="absolute inset-[3px] rounded-full bg-signal" />
              </span>
              <div
                className={
                  i % 2 === 1
                    ? "md:col-start-2 md:pl-10"
                    : "md:col-start-1 md:pr-10 md:text-right"
                }
              >
                <p className="font-mono text-[11px] text-muted-foreground">
                  {String(i + 1).padStart(2, "0")} · {s.m}
                </p>
                <h3 className="mt-1.5 text-[17px] font-semibold tracking-[-0.015em]">{s.k}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{s.d}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}