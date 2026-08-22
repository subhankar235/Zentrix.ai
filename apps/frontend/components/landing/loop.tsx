"use client";

import { motion } from "framer-motion";
import { SectionHeading } from "./section-heading";

const mae = [0.41, 0.36, 0.34, 0.27, 0.23, 0.19, 0.16, 0.14, 0.12, 0.11];

export function Loop() {
  const max = Math.max(...mae);

  return (
    <section id="loop" className="relative border-t border-border py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-5">
        <SectionHeading
          label="feature 03 · closed loop"
          title="It forecasts, then grades itself."
          desc="Conformal-calibrated LightGBM forecasts degradation before it hurts. A contextual Thompson-sampling bandit chooses what to try. Every real outcome is written back and compared to the prediction that produced it."
          align="center"
        />

        <div className="mt-14 grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <motion.div
            initial={{ opacity: 0, y: 22 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-70px" }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="rounded-xl border border-border bg-surface p-6"
          >
            <div className="flex items-baseline justify-between">
              <p className="mono-label text-muted-foreground">prediction error · MAE over retrains</p>
              <p className="font-mono text-xs text-verified">−73%</p>
            </div>
            <div className="mt-6 flex h-44 items-end gap-2.5">
              {mae.map((v, i) => (
                <motion.div
                  key={i}
                  initial={{ scaleY: 0 }}
                  whileInView={{ scaleY: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
                  style={{ height: `${(v / max) * 100}%`, transformOrigin: "bottom" }}
                  className="flex-1 rounded-t-[3px] bg-gradient-to-t from-signal/25 to-signal"
                />
              ))}
            </div>
            <div className="mt-3 flex justify-between font-mono text-[10px] text-muted-foreground">
              <span>iteration 1</span>
              <span>iteration 10</span>
            </div>
          </motion.div>

          <div className="grid gap-4">
            {[
              {
                t: "Conformal intervals",
                d: "Forecasts ship with calibrated bounds, so a wide interval reads as uncertainty instead of false confidence.",
              },
              {
                t: "Contextual bandit",
                d: "Thompson sampling picks which optimization to explore next, weighted by the context it has actually seen work.",
              },
              {
                t: "Drift-aware retraining",
                d: "Evidently watches data and prediction drift; the retrain worker promotes a new model version through MLflow only when it wins.",
              },
            ].map((c, i) => (
              <motion.div
                key={c.t}
                initial={{ opacity: 0, x: 18 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="rounded-xl border border-border bg-surface p-5"
              >
                <h3 className="font-display text-[15px] font-semibold tracking-tight">{c.t}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{c.d}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
