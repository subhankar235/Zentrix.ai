"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export function Cta() {
  return (
    <section id="cta" className="relative overflow-hidden border-t border-border py-24 md:py-32">
      <div className="grid-field pointer-events-none absolute inset-0 [mask-image:radial-gradient(60%_70%_at_50%_50%,black,transparent)]" />
      <div className="pointer-events-none absolute left-1/2 bottom-[-14rem] h-[26rem] w-[46rem] -translate-x-1/2 rounded-full bg-signal/14 blur-[120px]" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="relative mx-auto max-w-3xl px-5 text-center"
      >
        <h2 className="font-display text-3xl font-semibold tracking-[-0.03em] sm:text-5xl sm:leading-[1.05]">
          Point it at a connection string.
          <br />
          <span className="text-gradient-signal">Keep the approval button.</span>
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
          Works with Neon, RDS, Supabase or self-hosted Postgres. Read-only to start; every write is
          policy-gated, human-approved and reversible.
        </p>

        <form
          className="mx-auto mt-9 flex max-w-md flex-col gap-2 sm:flex-row"
          onSubmit={(e) => e.preventDefault()}
        >
          <input
            type="email"
            required
            placeholder="you@company.com"
            aria-label="Work email"
            className="h-11 flex-1 rounded-md border border-border bg-surface px-4 font-mono text-[13px] outline-none transition-colors placeholder:text-muted-foreground focus:border-signal"
          />
          <button
            type="submit"
            className="group inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 font-mono text-[13px] font-medium text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Request access
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </button>
        </form>
        <p className="mono-label mt-4 text-muted-foreground">
          no credentials leave your infrastructure unencrypted
        </p>
      </motion.div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-border py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 sm:flex-row">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-[6px] border border-signal/40 bg-signal/10">
            <span className="h-1 w-1 rounded-full bg-signal" />
          </span>
          <span className="font-mono text-xs text-muted-foreground">
            Zentrix — AI-powered database intelligence
          </span>
        </div>
        <div className="flex gap-6">
          {["Docs", "Architecture", "Security"].map((l) => (
            <a key={l} href="#top" className="mono-label text-muted-foreground hover:text-foreground">
              {l}
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
}
