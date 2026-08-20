"use client";

import { motion } from "framer-motion";
import { useTheme } from "next-themes";
import { AnimatedThemeToggler } from "@/components/ui/animated-theme-toggler";

const links = [
  { href: "#evidence", label: "Evidence" },
  { href: "#agents", label: "Agents" },
  { href: "#sandbox", label: "Sandbox" },
  { href: "#loop", label: "Closed loop" },
  { href: "#roi", label: "ROI" },
];

export function Nav() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <motion.header
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-x-0 top-0 z-50 border-b border-border/70 bg-background/70 backdrop-blur-xl"
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <a href="#top" className="group flex items-center gap-2.5">
          <span className="relative flex h-7 w-7 items-center justify-center rounded-[7px] border border-signal/40 bg-signal/10">
            <span className="h-1.5 w-1.5 rounded-full bg-signal shadow-[0_0_12px_var(--signal)]" />
          </span>
          <span className="font-display text-[15px] font-semibold tracking-tight">
            Zentrix
          </span>
        </a>

        <nav className="hidden items-center gap-7 md:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="mono-label text-muted-foreground transition-colors hover:text-foreground"
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <AnimatedThemeToggler
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            theme={resolvedTheme === "dark" ? "dark" : "light"}
            onThemeChange={setTheme}
          />
          <a
            href="#cta"
            className="inline-flex h-9 items-center rounded-md bg-primary px-4 font-mono text-xs font-medium tracking-wide text-primary-foreground transition-transform hover:-translate-y-px"
          >
            Connect database
          </a>
        </div>
      </div>
    </motion.header>
  );
}
