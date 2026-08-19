"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useThemeStore } from "@/stores/theme-store";

export function ThemeToggle() {
  const dark = useThemeStore((s) => s.dark);
  const toggle = useThemeStore((s) => s.toggle);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const isDark = stored ? stored === "dark" : true;
    useThemeStore.getState().setDark(isDark);
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark, mounted]);

  return (
    <button
      type="button"
      aria-label="Toggle color theme"
      onClick={toggle}
      className="relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface text-muted-foreground transition-colors hover:text-signal"
    >
      <Sun className={`h-4 w-4 transition-all ${dark ? "scale-0 rotate-90" : "scale-100 rotate-0"}`} />
      <Moon
        className={`absolute h-4 w-4 transition-all ${dark ? "scale-100 rotate-0" : "scale-0 -rotate-90"}`}
      />
    </button>
  );
}
