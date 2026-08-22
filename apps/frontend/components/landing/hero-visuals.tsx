"use client";

import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { motion } from "framer-motion";

const agents = [
  { id: "planner", label: "Planner", finding: "cardinality est. off 42×", weight: 0.91 },
  { id: "vacuum", label: "Vacuum", finding: "dead tuples 31% on orders", weight: 0.64 },
  { id: "locks", label: "Concurrency", finding: "no blocking chains", weight: 0.08 },
  { id: "io", label: "I/O · Buffer", finding: "temp spill 1.2 GB", weight: 0.47 },
  { id: "index", label: "Schema · Index", finding: "missing idx (org_id, created_at)", weight: 0.88 },
];

const stages = ["Collecting evidence", "Specialist agents", "Supervisor reconcile", "Verdict"];

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(callback: () => void) {
  const mql = window.matchMedia(REDUCED_MOTION_QUERY);
  mql.addEventListener("change", callback);
  return () => mql.removeEventListener("change", callback);
}

export function HeroVisual() {
  const [step, setStep] = useState(0);
  const reduced = useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setStep((s) => (s + 1) % 4), 2200);
    return () => clearInterval(id);
  }, [reduced]);

  // Reduced-motion users see the completed state without any animation.
  const active = reduced ? 3 : step;

  return (
    <div className="mx-auto max-w-6xl px-5 pb-24 md:pb-32">
      <div className="relative overflow-hidden rounded-xl border border-border bg-card shadow-instrument">
      {/* window bar */}
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-signal" />
          <span className="truncate font-mono text-[11px] text-muted-foreground">
            diagnosis · conn/prod-eu-1 · p95 840ms ↑
          </span>
        </div>
        <span className="hidden shrink-0 font-mono text-[10px] tracking-widest text-muted-foreground uppercase sm:block">
          read-only
        </span>
      </div>

      {/* stage rail */}
      <div className="grid grid-cols-4 border-b border-border">
        {stages.map((s, i) => (
          <div key={s} className="relative px-2 py-2 text-center">
            <span
              className={`font-mono text-[9.5px] tracking-wider uppercase transition-colors duration-500 ${
                i <= active ? "text-foreground" : "text-muted-foreground/60"
              }`}
            >
              {s}
            </span>
            {i <= active && (
              <motion.span
                layoutId="stage-underline"
                className="absolute inset-x-2 -bottom-px h-px bg-signal"
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              />
            )}
          </div>
        ))}
      </div>

      <div className="grid gap-0 md:grid-cols-[1fr_0.9fr]">
        {/* agents */}
        <div className="divide-y divide-border border-b border-border md:border-r md:border-b-0">
          {agents.map((a, i) => {
            const agentActive = active >= 1;
            return (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.25 + i * 0.08, duration: 0.5 }}
                className="flex items-center gap-3 px-4 py-2.5"
              >
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full transition-colors duration-500 ${
                    agentActive
                      ? a.weight > 0.6
                        ? "bg-signal"
                        : a.weight > 0.3
                          ? "bg-warn"
                          : "bg-muted-foreground/40"
                      : "bg-muted-foreground/25"
                  }`}
                />
                <span className="w-24 shrink-0 truncate text-[12.5px] font-medium">{a.label}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-muted-foreground">
                  {agentActive ? a.finding : "…"}
                </span>
                <div className="hidden h-1 w-14 shrink-0 overflow-hidden rounded-full bg-surface-2 sm:block">
                  <motion.div
                    className="h-full bg-foreground/70"
                    initial={{ width: 0 }}
                    animate={{ width: agentActive ? `${a.weight * 100}%` : 0 }}
                    transition={{ duration: 0.8, delay: 0.3 + i * 0.08 }}
                  />
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* verdict */}
        <div className="flex flex-col gap-3 p-4">
          <p className="mono-label text-muted-foreground">Supervisor report</p>
          <p className="text-[13.5px] leading-relaxed">
            Root cause: stale statistics on{" "}
            <span className="font-mono text-[12.5px] text-signal">orders.org_id</span> flipped the
            plan from index scan to seq scan.
          </p>
          <div className="rounded-md border border-border bg-surface p-3">
            <p className="font-mono text-[11px] text-muted-foreground">candidate</p>
            <p className="mt-1 font-mono text-[11.5px] break-words">
              CREATE INDEX CONCURRENTLY ON orders (org_id, created_at);
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge tone="signal" show={active >= 3}>
                shadow-verified −71% p95
              </Badge>
              <Badge tone="muted" show={active >= 3}>
                p = 0.003
              </Badge>
              <Badge tone="warn" show={active >= 3}>
                awaiting approval
              </Badge>
            </div>
          </div>
          <p className="font-mono text-[10.5px] text-muted-foreground">
            no production write until a human approves · canary + auto-rollback
          </p>
        </div>
      </div>
      </div>
    </div>
  );
}

function Badge({
  children,
  tone,
  show,
}: {
  children: ReactNode;
  tone: "signal" | "warn" | "muted";
  show: boolean;
}) {
  const tones = {
    signal: "border-signal/40 text-signal",
    warn: "border-warn/40 text-warn",
    muted: "border-border text-muted-foreground",
  } as const;
  return (
    <motion.span
      animate={{ opacity: show ? 1 : 0.25, y: show ? 0 : 4 }}
      transition={{ duration: 0.4 }}
      className={`rounded-full border px-2 py-0.5 font-mono text-[10.5px] ${tones[tone]}`}
    >
      {children}
    </motion.span>
  );
}