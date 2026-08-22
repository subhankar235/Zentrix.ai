"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { SectionHeading } from "./section-heading";

function Counter({ value, prefix = "", suffix = "" }: { value: number; prefix?: string; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const [n, setN] = useState(0);

  useEffect(() => {
    if (!inView) return;
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min((t - start) / 1400, 1);
      setN(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value]);

  return (
    <span ref={ref} className="font-display text-4xl font-semibold tracking-tight sm:text-5xl">
      {prefix}
      {n.toLocaleString()}
      {suffix}
    </span>
  );
}

export function Roi() {
  return (
    <section id="roi" className="relative border-t border-border py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-5">
        <div className="grid gap-14 lg:grid-cols-2 lg:items-center">
          <SectionHeading
            label="feature 04 · roi"
            title="Milliseconds, translated into dollars."
            desc="A pure deterministic calculation over verified experiment outcomes — no model, no agent, no rounding in your favour. Compute time reclaimed, I/O avoided, and engineer-hours not spent staring at EXPLAIN output."
          />

          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border">
            {[
              { v: 18400, prefix: "$", suffix: "", k: "annualized compute saved" },
              { v: 71, prefix: "", suffix: "%", k: "p95 latency reduction" },
              { v: 126, prefix: "", suffix: " h", k: "DBA hours returned" },
              { v: 43, prefix: "", suffix: "", k: "verified optimizations" },
            ].map((m, i) => (
              <motion.div
                key={m.k}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="bg-surface px-6 py-8"
              >
                <Counter value={m.v} prefix={m.prefix} suffix={m.suffix} />
                <p className="mono-label mt-2 text-muted-foreground">{m.k}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
