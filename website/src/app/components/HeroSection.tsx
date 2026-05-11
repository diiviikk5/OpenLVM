"use client";

import { motion } from "framer-motion";
import { ArrowRight, Terminal, GitFork, Sparkles } from "lucide-react";
import Link from "next/link";

const codeLines = [
  { text: "$ openlvm test swarm.yaml --scenarios 5000 --chaos all", delay: 0, color: "" },
  { text: "", delay: 0.3, color: "" },
  { text: "  ⚡ Forking agent graph... 5000 universes in 4.2ms", delay: 0.6, color: "text-accent-emerald" },
  { text: "  🔀 Injecting chaos: network_delay, hallucination, api_error", delay: 0.9, color: "text-accent-amber" },
  { text: "  📊 Running DeepEval metrics: TaskCompletion, ToolCorrectness", delay: 1.2, color: "text-coral" },
  { text: "  🛡️ Promptfoo red-team: function_discovery, injection", delay: 1.5, color: "text-accent-coral-status" },
  { text: "", delay: 1.8, color: "" },
  { text: "  ✓ 4,847 passed  ⚠ 142 warnings  ✗ 11 failures", delay: 2.1, color: "text-accent-emerald" },
  { text: "  → Agent C poisoned shared DB via Agent A drift (#3847)", delay: 2.4, color: "text-accent-coral-status" },
  { text: "  → Replay: openlvm://replay/3847", delay: 2.7, color: "text-coral" },
];

export default function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center overflow-hidden pt-16">
      {/* Background decoration */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: `linear-gradient(rgba(176,174,165,1) 1px, transparent 1px), linear-gradient(90deg, rgba(176,174,165,1) 1px, transparent 1px)`,
            backgroundSize: "64px 64px",
          }}
        />
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-brand-glow blur-[120px] opacity-50" />
        <div className="absolute bottom-1/4 right-1/4 w-[300px] h-[300px] rounded-full bg-brand-glow blur-[100px] opacity-25" />
      </div>

      <div className="relative max-w-[1200px] mx-auto px-6 lg:px-8 py-20 lg:py-28">
        <div className="grid lg:grid-cols-2 gap-16 lg:gap-12 items-center">
          {/* Left: Copy */}
          <motion.div
            initial={{ opacity: 0, y: 32 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 mb-8 rounded-full border border-border-dark bg-dark-surface text-[13px] text-warm-silver shadow-[0_0_0_1px_rgba(48,48,46,0.6)]"
            >
              <Sparkles className="w-3.5 h-3.5 text-terracotta" />
              <span>Open Source · Apache 2.0 · Zig + Python</span>
            </motion.div>

            <h1 className="font-[family-name:var(--font-serif)] text-[clamp(2.5rem,5vw,4rem)] font-medium leading-[1.10] tracking-tight text-ivory mb-6">
              The runtime your
              <br />
              agents{" "}
              <span className="text-terracotta relative">
                deserve
                <svg className="absolute -bottom-1 left-0 w-full h-3" viewBox="0 0 200 12" preserveAspectRatio="none">
                  <path d="M0 8 Q50 0 100 6 Q150 12 200 4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="opacity-40" />
                </svg>
              </span>
            </h1>

            <p className="text-[1.15rem] leading-[1.65] text-warm-silver max-w-[520px] mb-10">
              Fork 5,000 parallel agent worlds in under 5ms. Test with DeepEval metrics. Red-team with Promptfoo. Trace with OpenTelemetry. Replay failures deterministically.{" "}
              <span className="text-ivory font-medium">One tool. Zero compromises.</span>
            </p>

            <div className="flex flex-wrap gap-3.5">
              <Link
                href="/workbench#quick-run"
                className="group inline-flex items-center gap-2 px-5 py-2.5 text-[15px] font-medium text-ivory bg-terracotta rounded-xl hover:bg-coral transition-all duration-300 shadow-[0_0_0_1px_rgba(201,100,66,0.4)] hover:shadow-[0_0_24px_rgba(201,100,66,0.3)]"
              >
                <Terminal className="w-4 h-4" />
                pip install openlvm
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link
                href="/#capabilities"
                className="inline-flex items-center gap-2 px-5 py-2.5 text-[15px] font-medium text-warm-silver bg-dark-surface rounded-xl hover:bg-olive-gray/20 transition-all duration-200 shadow-[0_0_0_1px_rgba(48,48,46,0.8)] border border-border-dark"
              >
                <GitFork className="w-4 h-4" />
                See How It Works
              </Link>
            </div>

            {/* Stats */}
            <div className="flex gap-8 mt-12 pt-8 border-t border-border-dark">
              {[
                { value: "<5ms", label: "Fork latency" },
                { value: "5000+", label: "Parallel worlds" },
                { value: "30+", label: "Eval metrics" },
              ].map((stat, i) => (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.8 + i * 0.15 }}
                >
                  <div className="text-2xl font-semibold text-ivory">{stat.value}</div>
                  <div className="text-[13px] text-stone-gray mt-0.5">{stat.label}</div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Right: Terminal */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="relative"
          >
            <div className="rounded-2xl overflow-hidden terminal-shadow bg-deep-dark">
              {/* Terminal header */}
              <div className="flex items-center gap-2 px-4 py-3 bg-dark-surface border-b border-border-dark">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-accent-coral-status/80" />
                  <div className="w-3 h-3 rounded-full bg-accent-amber/80" />
                  <div className="w-3 h-3 rounded-full bg-accent-emerald/80" />
                </div>
                <span className="text-[12px] text-stone-gray ml-2 font-[family-name:var(--font-mono)]">
                  openlvm — swarm test
                </span>
              </div>

              {/* Terminal body */}
              <div className="p-5 font-[family-name:var(--font-mono)] text-[13px] leading-[1.7] min-h-[320px]">
                {codeLines.map((line, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: line.delay + 0.8, duration: 0.4 }}
                    className={`${line.color || "text-warm-silver"} ${line.text === "" ? "h-4" : ""}`}
                  >
                    {line.text}
                  </motion.div>
                ))}
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 3.8 }}
                  className="inline-block w-2 h-4 bg-coral mt-1 animate-terminal-blink"
                />
              </div>
            </div>

            {/* Floating badges */}
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 1.5, duration: 0.5 }}
              className="absolute -top-4 -right-4 px-3 py-1.5 rounded-lg glass-dark-elevated text-[12px] font-medium text-terracotta animate-float"
            >
              ⚡ Zig-powered core
            </motion.div>
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 1.8, duration: 0.5 }}
              className="absolute -bottom-3 -left-4 px-3 py-1.5 rounded-lg glass-dark-elevated text-[12px] font-medium text-warm-silver animate-float"
              style={{ animationDelay: "2s" }}
            >
              🧪 30+ eval metrics
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
