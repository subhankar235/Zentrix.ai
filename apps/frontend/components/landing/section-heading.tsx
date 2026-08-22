"use client";

import { motion } from "framer-motion";

export function SectionHeading({
  label,
  title,
  desc,
  align = "left",
}: {
  label: string;
  title: string;
  desc?: string;
  align?: "left" | "center";
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-2xl"}
    >
      <div className={`flex items-center gap-3 ${align === "center" ? "justify-center" : ""}`}>
        <span className="h-px w-8 bg-signal" />
        <span className="mono-label text-signal">{label}</span>
      </div>
      <h2 className="mt-4 font-display text-3xl font-semibold tracking-[-0.03em] sm:text-[2.6rem] sm:leading-[1.08]">
        {title}
      </h2>
      {desc ? <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">{desc}</p> : null}
    </motion.div>
  );
}
