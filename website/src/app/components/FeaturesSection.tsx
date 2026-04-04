"use client";

import { motion } from "framer-motion";
import {
  GitFork,
  Play,
  ShieldCheck,
  Zap,
  Eye,
  Database,
  Waves,
  Lock,
} from "lucide-react";

const features = [
  {
    icon: GitFork,
    title: "Zero-Cost CoW Forks",
    description:
      "Fork entire agent graphs — memory, tool state, conversation history — in under 5ms via OS-level Copy-on-Write. No serialization. No Docker overhead.",
    accent: "bg-terracotta/10 text-terracotta",
    tag: "Core",
  },
  {
    icon: Play,
    title: "Deterministic Replay",
    description:
      "Record every non-deterministic event (LLM responses, tool results, timestamps) and replay them verbatim. Debug multi-agent cascading failures in minutes, not days.",
    accent: "bg-accent-emerald/10 text-accent-emerald",
    tag: "Debug",
  },
  {
    icon: ShieldCheck,
    title: "Built-in Red Teaming",
    description:
      "Promptfoo vulnerability scans + DeepEval safety metrics run automatically across thousands of chaotic simulations inside isolated sandboxes.",
    accent: "bg-accent-coral-status/10 text-accent-coral-status",
    tag: "Security",
  },
  {
    icon: Eye,
    title: "Auto OpenTelemetry",
    description:
      "Every LLM call, tool use, agent step, and vector DB query is auto-instrumented with OpenLLMetry traces. Zero configuration, full observability.",
    accent: "bg-accent-amber/10 text-accent-amber",
    tag: "Observe",
  },
  {
    icon: Waves,
    title: "Chaos Simulation",
    description:
      "Inject network delays, API errors, hallucination corruption, memory pressure, and clock skew. Find failures before they find your users.",
    accent: "bg-coral/10 text-coral",
    tag: "Test",
  },
  {
    icon: Lock,
    title: "Per-Agent Capabilities",
    description:
      "Fine-grained capability revocation per agent. Network? Filesystem? Shared DB writes? Each agent gets exactly the permissions it needs. Nothing more.",
    accent: "bg-accent-emerald/10 text-accent-emerald",
    tag: "Safety",
  },
  {
    icon: Zap,
    title: "30+ Eval Metrics",
    description:
      "Task Completion, Tool Correctness, Plan Adherence, Hallucination, Faithfulness, and 25+ more DeepEval metrics run natively on every simulation branch.",
    accent: "bg-terracotta/10 text-terracotta",
    tag: "Eval",
  },
  {
    icon: Database,
    title: "EvalStore Versioning",
    description:
      "Built-in SQLite result database. Query how any agent behaved across the last 50 runs. Compare, diff, and detect regressions automatically.",
    accent: "bg-accent-amber/10 text-accent-amber",
    tag: "Track",
  },
];

export default function FeaturesSection() {
  return (
    <section id="features" className="relative py-24 lg:py-32 bg-dark-surface">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-8">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block px-3 py-1 mb-4 text-[12px] font-medium tracking-[0.5px] uppercase text-terracotta bg-brand-glow rounded-full">
            Features
          </span>
          <h2 className="font-[family-name:var(--font-serif)] text-[clamp(2rem,4vw,3.25rem)] font-medium leading-[1.15] text-ivory mb-4">
            Everything your agents need,
            <br />
            nothing they don&apos;t
          </h2>
          <p className="text-[1.1rem] leading-[1.65] text-warm-silver max-w-[600px] mx-auto">
            Cherry-picked from the best tools in the ecosystem — OpenLLMetry,
            Promptfoo, DeepEval — and fused with a performance-tight Zig runtime.
          </p>
        </motion.div>

        {/* Feature grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.06 }}
              className="group relative p-6 rounded-2xl bg-near-black border border-border-dark hover:border-olive-gray/40 transition-all duration-300 hover:shadow-[0_0_0_1px_rgba(48,48,46,0.8)] cursor-default"
            >
              {/* Tag */}
              <span className="inline-block px-2 py-0.5 mb-4 text-[11px] font-medium tracking-[0.3px] uppercase text-stone-gray bg-dark-surface rounded">
                {feature.tag}
              </span>

              {/* Icon */}
              <div className={`w-10 h-10 rounded-xl ${feature.accent} flex items-center justify-center mb-4`}>
                <feature.icon className="w-5 h-5" />
              </div>

              {/* Content */}
              <h3 className="font-[family-name:var(--font-serif)] text-[1.15rem] font-medium text-ivory mb-2 leading-[1.25]">
                {feature.title}
              </h3>
              <p className="text-[14px] leading-[1.6] text-warm-silver">
                {feature.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
