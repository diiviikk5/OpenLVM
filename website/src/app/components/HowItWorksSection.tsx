"use client";

import { motion } from "framer-motion";
import { GitFork, Zap, Eye, BarChart3 } from "lucide-react";

const steps = [
  {
    number: "01",
    icon: GitFork,
    title: "Define Your Agent Swarm",
    description:
      "Write a simple YAML config describing your agents, their capabilities, dependencies, and the chaos scenarios you want to test.",
    code: `agents:
  researcher:
    entry: agents/researcher.py
    capabilities: [llm_call, tool_use]
  planner:
    entry: agents/planner.py
    depends_on: [researcher]
  executor:
    entry: agents/executor.py
    capabilities: [llm_call, network]`,
    accent: "border-terracotta",
  },
  {
    number: "02",
    icon: Zap,
    title: "Fork Thousands of Worlds",
    description:
      "OpenLVM forks the entire agent graph — memory, tool state, conversation — in under 5ms per world using OS-level Copy-on-Write. No Docker. No cold starts.",
    code: `$ openlvm test swarm.yaml --scenarios 5000

⚡ Forking 5000 universes... done in 4.2ms
📊 Memory: 12MB base + 2.3MB CoW delta
🔄 All forks share base pages until diverge`,
    accent: "border-accent-emerald",
  },
  {
    number: "03",
    icon: Eye,
    title: "Inject Chaos & Observe",
    description:
      "Each forked world gets chaos injection (network delays, API errors, hallucination corruption) while OpenTelemetry auto-traces every LLM call and tool use.",
    code: `chaos:
  - type: hallucination
    target: researcher
    params: { corruption_rate: 0.1 }
  - type: api_error
    target: executor
    params: { error_code: 429 }`,
    accent: "border-accent-amber",
  },
  {
    number: "04",
    icon: BarChart3,
    title: "Eval, Compare, Ship",
    description:
      "DeepEval metrics + Promptfoo red-team scans run on every branch. Results are versioned in EvalStore. Regressions trigger alerts. You ship with confidence.",
    code: `✓ 4,847 passed  ⚠ 142 warnings  ✗ 11 failures

Metrics:
  TaskCompletion:    0.94 (↑ 0.02 from last run)
  ToolCorrectness:   0.91
  PlanAdherence:     0.87 (⚠ regression)
  Hallucination:     0.03 (↓ 0.01 ✓)`,
    accent: "border-coral",
  },
];

export default function HowItWorksSection() {
  return (
    <section id="how-it-works" className="relative py-24 lg:py-32 bg-near-black">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-8">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <span className="inline-block px-3 py-1 mb-4 text-[12px] font-medium tracking-[0.5px] uppercase text-coral bg-brand-glow rounded-full">
            How It Works
          </span>
          <h2 className="font-[family-name:var(--font-serif)] text-[clamp(2rem,4vw,3.25rem)] font-medium leading-[1.15] text-ivory mb-4">
            From YAML to production-safe
            <br />
            agents in four steps
          </h2>
          <p className="text-[1.1rem] leading-[1.65] text-warm-silver max-w-[550px] mx-auto">
            No Docker. No Firecracker cold starts. Just define, fork, test, ship.
          </p>
        </motion.div>

        {/* Steps */}
        <div className="space-y-8">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.6, delay: i * 0.1 }}
              className={`relative grid lg:grid-cols-2 gap-8 p-8 lg:p-10 rounded-2xl bg-dark-surface border-l-2 ${step.accent} border border-border-dark`}
            >
              {/* Left: Content */}
              <div className="flex flex-col justify-center">
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-[13px] font-mono font-semibold text-coral">
                    {step.number}
                  </span>
                  <div className="w-8 h-8 rounded-lg bg-brand-glow flex items-center justify-center">
                    <step.icon className="w-4 h-4 text-coral" />
                  </div>
                </div>
                <h3 className="font-[family-name:var(--font-serif)] text-[1.6rem] font-medium text-ivory mb-3 leading-[1.25]">
                  {step.title}
                </h3>
                <p className="text-[15px] leading-[1.65] text-warm-silver">
                  {step.description}
                </p>
              </div>

              {/* Right: Code block */}
              <div className="rounded-xl bg-near-black border border-border-dark overflow-hidden">
                <div className="px-4 py-2.5 border-b border-border-dark flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-accent-coral-status/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-accent-amber/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-accent-emerald/60" />
                </div>
                <pre className="p-5 text-[13px] leading-[1.7] text-warm-silver font-[family-name:var(--font-mono)] overflow-x-auto">
                  {step.code}
                </pre>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
