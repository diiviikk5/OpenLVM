"use client";

import { motion } from "framer-motion";

const layers = [
  {
    name: "User Layer",
    color: "border-terracotta",
    bg: "bg-terracotta/5",
    items: [
      { label: "CLI", desc: "openlvm test / fork / replay" },
      { label: "MCP Server", desc: "Cursor / Claude Code integration" },
      { label: "Python SDK", desc: "pip install openlvm" },
      { label: "YAML Config", desc: "Declarative test suites" },
    ],
  },
  {
    name: "Orchestration Layer (Python)",
    color: "border-accent-amber",
    bg: "bg-accent-amber/5",
    items: [
      { label: "Test Orchestrator", desc: "Fork → chaos → eval pipeline" },
      { label: "Eval Engine", desc: "DeepEval + Promptfoo adapters" },
      { label: "OTel Collector", desc: "OpenLLMetry auto-instrumentation" },
      { label: "EvalStore", desc: "SQLite result versioning" },
    ],
  },
  {
    name: "Core Runtime (Zig)",
    color: "border-accent-emerald",
    bg: "bg-accent-emerald/5",
    items: [
      { label: "CoW Fork Engine", desc: "<5ms zero-copy forks" },
      { label: "Sandbox Manager", desc: "seccomp + namespaces" },
      { label: "Replay Engine", desc: "Deterministic event playback" },
      { label: "Capability System", desc: "Per-agent permission masks" },
    ],
  },
];

export default function ArchitectureSection() {
  return (
    <section id="architecture" className="relative py-24 lg:py-32 bg-dark-surface">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block px-3 py-1 mb-4 text-[12px] font-medium tracking-[0.5px] uppercase text-terracotta bg-brand-glow rounded-full">
            Architecture
          </span>
          <h2 className="font-[family-name:var(--font-serif)] text-[clamp(2rem,4vw,3.25rem)] font-medium leading-[1.15] text-ivory mb-4">
            Three layers, one binary
          </h2>
          <p className="text-[1.1rem] leading-[1.65] text-warm-silver max-w-[550px] mx-auto">
            Zig handles the hot path. Python handles the ecosystem. They meet at a thin C-ABI boundary.
          </p>
        </motion.div>

        {/* Layers */}
        <div className="space-y-6 max-w-[900px] mx-auto">
          {layers.map((layer, li) => (
            <motion.div
              key={layer.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: li * 0.1 }}
              className={`rounded-2xl border ${layer.color} ${layer.bg} overflow-hidden`}
            >
              <div className={`px-6 py-3.5 border-b ${layer.color}`}>
                <h3 className="font-[family-name:var(--font-mono)] text-[14px] font-semibold text-ivory tracking-tight">
                  {layer.name}
                </h3>
              </div>
              <div className="p-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {layer.items.map((item) => (
                  <div
                    key={item.label}
                    className="px-4 py-3 rounded-xl bg-near-black/80 border border-border-dark"
                  >
                    <div className="text-[14px] font-semibold text-ivory mb-0.5">
                      {item.label}
                    </div>
                    <div className="text-[12px] text-stone-gray leading-[1.5]">
                      {item.desc}
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}

          {/* Connector lines */}
          <div className="flex justify-center -mt-3">
            <div className="flex flex-col items-center gap-1 text-stone-gray">
              <div className="w-px h-4 bg-border-dark" />
              <span className="text-[11px] font-[family-name:var(--font-mono)] px-2 py-0.5 bg-near-black rounded text-warm-silver border border-border-dark">
                C-ABI / ctypes FFI
              </span>
              <div className="w-px h-4 bg-border-dark" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
