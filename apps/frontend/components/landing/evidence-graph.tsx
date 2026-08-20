"use client";

import { motion } from "framer-motion";

type Node = { id: string; x: number; y: number; label: string; sub: string; kind: "src" | "mid" | "out" };

const nodes: Node[] = [
  { id: "stmts", x: 20, y: 18, label: "pg_stat_statements", sub: "+412% mean_exec", kind: "src" },
  { id: "stats", x: 18, y: 52, label: "pg_stats", sub: "stale 19d", kind: "src" },
  { id: "locks", x: 20, y: 84, label: "pg_locks", sub: "no chain", kind: "src" },
  { id: "plan", x: 50, y: 32, label: "plan flip", sub: "index → seq scan", kind: "mid" },
  { id: "card", x: 52, y: 68, label: "cardinality err", sub: "est 1.2k / act 940k", kind: "mid" },
  { id: "root", x: 86, y: 50, label: "root cause", sub: "stale statistics", kind: "out" },
];

const edges: Array<[string, string]> = [
  ["stmts", "plan"],
  ["stats", "plan"],
  ["stats", "card"],
  ["locks", "card"],
  ["plan", "root"],
  ["card", "root"],
];

const byId = Object.fromEntries(nodes.map((n) => [n.id, n])) as Record<string, Node>;

export function EvidenceGraph() {
  return (
    <div className="relative rounded-xl border border-border bg-surface p-4 shadow-instrument">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <span className="mono-label text-muted-foreground">evidence graph · conn_7f2a</span>
        <span className="mono-label rounded-sm bg-verified/12 px-2 py-0.5 text-verified">confidence 0.94</span>
      </div>

      <div className="relative mt-4 h-[320px] w-full overflow-hidden rounded-lg bg-background/60 grid-field">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          {edges.map(([a, b], i) => {
            const from = byId[a]!;
            const to = byId[b]!;
            const mx = (from.x + to.x) / 2;
            return (
              <g key={`${a}-${b}`}>
                <path
                  d={`M ${from.x} ${from.y} C ${mx} ${from.y}, ${mx} ${to.y}, ${to.x} ${to.y}`}
                  fill="none"
                  stroke="var(--border)"
                  strokeWidth="0.35"
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d={`M ${from.x} ${from.y} C ${mx} ${from.y}, ${mx} ${to.y}, ${to.x} ${to.y}`}
                  fill="none"
                  stroke="var(--signal)"
                  strokeWidth="1"
                  strokeDasharray="6 22"
                  vectorEffect="non-scaling-stroke"
                  style={{ animation: `trace-dash ${5 + i * 0.4}s linear infinite` }}
                />
              </g>
            );
          })}
        </svg>

        {nodes.map((n, i) => (
          <div
            key={n.id}
            className="absolute z-10"
            style={{ left: `${n.x}%`, top: `${n.y}%`, transform: "translate(-50%, -50%)" }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.85 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: 0.35 + i * 0.09, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className={`whitespace-nowrap rounded-md border px-2.5 py-1.5 backdrop-blur-sm ${
                n.kind === "out"
                  ? "border-signal/60 bg-signal/12 shadow-glow"
                  : n.kind === "mid"
                    ? "border-warn/45 bg-warn/8"
                    : "border-border bg-surface"
              }`}
            >
              <div className="font-mono text-[10.5px] leading-tight font-medium">{n.label}</div>
              <div className="font-mono text-[9.5px] leading-tight text-muted-foreground">{n.sub}</div>
            </motion.div>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-1.5 font-mono text-[11px] text-muted-foreground">
        <p>
          <span className="text-signal">supervisor</span> · reconciled 5 specialist hypotheses
        </p>
        <p>
          <span className="text-warn">validation plan</span> · ANALYZE public.orders → re-EXPLAIN → shadow replay
        </p>
      </div>
    </div>
  );
}
