"use client";

import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Activity } from "lucide-react";
import { EvidenceGraph } from "./evidence-graph";

const ease = [0.22, 1, 0.36, 1] as const;

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden pt-32 pb-24 md:pt-40 md:pb-32">
      <div className="grid-field pointer-events-none absolute inset-0 [mask-image:radial-gradient(70%_60%_at_50%_20%,black,transparent)]" />
      <div className="pointer-events-none absolute left-1/2 top-[-12rem] h-[28rem] w-[52rem] -translate-x-1/2 rounded-full bg-signal/12 blur-[120px]" />

      <div className="relative mx-auto grid max-w-6xl gap-14 px-5 lg:grid-cols-[1.05fr_1fr] lg:items-center">
        <div>
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease }}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-verified opacity-70" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-verified" />
            </span>
            <span className="mono-label text-muted-foreground">Evidence-first Postgres intelligence</span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.75, delay: 0.06, ease }}
            className="mt-6 font-display text-[2.7rem] leading-[1.03] font-semibold tracking-[-0.03em] sm:text-6xl"
          >
            A DBA that <span className="text-gradient-signal">proves</span> it,
            <br />
            before it touches prod.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.75, delay: 0.14, ease }}
            className="mt-6 max-w-xl text-[15px] leading-relaxed text-muted-foreground"
          >
            Most tools hand raw metrics to an LLM and print a guess. This one collects deterministic
            evidence from Postgres internals, builds a causal diagnosis with specialist agents,
            simulates every fix in a shadow clone, and only then asks for your approval.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.75, delay: 0.22, ease }}
            className="mt-9 flex flex-wrap items-center gap-3"
          >
            <a
              href="#cta"
              className="group inline-flex h-11 items-center gap-2 rounded-md bg-primary px-5 font-mono text-[13px] font-medium text-primary-foreground shadow-instrument transition-transform hover:-translate-y-0.5"
            >
              Run a diagnosis
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </a>
            <a
              href="#evidence"
              className="inline-flex h-11 items-center gap-2 rounded-md border border-border bg-surface px-5 font-mono text-[13px] text-foreground transition-colors hover:border-signal/50"
            >
              See the evidence chain
            </a>
          </motion.div>

          <motion.dl
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.35 }}
            className="mt-12 grid max-w-lg grid-cols-3 gap-px overflow-hidden rounded-lg border border-border bg-border"
          >
            {[
              { k: "Read-only", v: "telemetry", icon: Activity },
              { k: "0", v: "unverified writes", icon: ShieldCheck },
              { k: "p < 0.05", v: "before deploy", icon: null },
            ].map((s) => (
              <div key={s.v} className="bg-surface px-4 py-4">
                <dt className="font-display text-lg font-semibold tracking-tight">{s.k}</dt>
                <dd className="mono-label mt-1 text-muted-foreground">{s.v}</dd>
              </div>
            ))}
          </motion.dl>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 24 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.2, ease }}
        >
          <EvidenceGraph />
        </motion.div>
      </div>
    </section>
  );
}
