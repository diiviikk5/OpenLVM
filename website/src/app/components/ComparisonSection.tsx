"use client";

import { motion } from "framer-motion";
import { Check, X, Minus } from "lucide-react";

type CellValue = "yes" | "no" | "partial" | string;

const columns = ["OpenLVM", "OpenLLMetry", "Promptfoo", "DeepEval", "E2B"];

const rows: { feature: string; values: CellValue[] }[] = [
  { feature: "CLI", values: ["yes", "no", "yes", "yes", "partial"] },
  { feature: "MCP Server", values: ["yes", "yes", "no", "yes", "no"] },
  { feature: "Auto OTel Traces", values: ["yes", "yes", "no", "partial", "no"] },
  { feature: "Red-team / Vuln Scan", values: ["yes", "no", "yes", "partial", "no"] },
  { feature: "30+ Eval Metrics", values: ["yes", "no", "partial", "yes", "no"] },
  { feature: "Agent Sandbox", values: ["yes", "no", "no", "no", "yes"] },
  { feature: "<5ms CoW Forks", values: ["yes", "no", "no", "no", "no"] },
  { feature: "Deterministic Replay", values: ["yes", "no", "no", "no", "no"] },
  { feature: "Chaos Injection", values: ["yes", "no", "no", "no", "no"] },
  { feature: "Per-Agent Capabilities", values: ["yes", "no", "no", "no", "no"] },
  { feature: "Result Versioning DB", values: ["yes", "no", "partial", "yes", "no"] },
];

function CellIcon({ value }: { value: CellValue }) {
  if (value === "yes") return <Check className="w-4 h-4 text-accent-emerald" />;
  if (value === "no") return <X className="w-4 h-4 text-stone-gray/50" />;
  if (value === "partial") return <Minus className="w-4 h-4 text-accent-amber" />;
  return <span className="text-[13px] text-warm-silver">{value}</span>;
}

export default function ComparisonSection() {
  return (
    <section id="comparison" className="relative py-24 lg:py-32 bg-dark-surface">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block px-3 py-1 mb-4 text-[12px] font-medium tracking-[0.5px] uppercase text-coral bg-brand-glow rounded-full">
            Comparison
          </span>
          <h2 className="font-[family-name:var(--font-serif)] text-[clamp(2rem,4vw,3.25rem)] font-medium leading-[1.15] text-ivory mb-4">
            We&apos;re not competing —
            <br />
            we&apos;re completing the stack
          </h2>
          <p className="text-[1.1rem] leading-[1.65] text-warm-silver max-w-[550px] mx-auto">
            Everyone solves half the problem. OpenLVM solves both halves in one tight binary.
          </p>
        </motion.div>

        {/* Table */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-50px" }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="overflow-x-auto rounded-2xl border border-border-dark bg-near-black"
        >
          <table className="w-full min-w-[700px]">
            <thead>
              <tr className="border-b border-border-dark">
                <th className="px-6 py-4 text-left text-[13px] font-medium text-stone-gray">
                  Feature
                </th>
                {columns.map((col, i) => (
                  <th
                    key={col}
                    className={`px-4 py-4 text-center text-[13px] font-semibold ${
                      i === 0
                        ? "text-terracotta bg-brand-glow"
                        : "text-warm-silver"
                    }`}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr
                  key={row.feature}
                  className={`border-b border-border-dark/50 ${
                    ri % 2 === 0 ? "" : "bg-dark-surface/30"
                  }`}
                >
                  <td className="px-6 py-3.5 text-[14px] text-warm-silver font-medium">
                    {row.feature}
                  </td>
                  {row.values.map((val, vi) => (
                    <td
                      key={vi}
                      className={`px-4 py-3.5 text-center ${
                        vi === 0 ? "bg-brand-glow" : ""
                      }`}
                    >
                      <div className="flex justify-center">
                        <CellIcon value={val} />
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </motion.div>

        {/* Legend */}
        <div className="flex justify-center gap-6 mt-6">
          {[
            { icon: <Check className="w-3.5 h-3.5 text-accent-emerald" />, label: "Full support" },
            { icon: <Minus className="w-3.5 h-3.5 text-accent-amber" />, label: "Partial" },
            { icon: <X className="w-3.5 h-3.5 text-stone-gray/50" />, label: "Not available" },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-1.5">
              {item.icon}
              <span className="text-[12px] text-stone-gray">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
