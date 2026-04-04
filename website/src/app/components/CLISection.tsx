"use client";

import { motion } from "framer-motion";
import { Copy, Check } from "lucide-react";
import { useState } from "react";

const commands = [
  {
    label: "Test your swarm",
    cmd: "openlvm test swarm.yaml --scenarios 5000 --chaos all",
  },
  {
    label: "Fork an agent",
    cmd: "openlvm fork agent-42 --count 100",
  },
  {
    label: "Replay a failure",
    cmd: "openlvm replay rec-3847 --trace --deepeval",
  },
  {
    label: "Compare runs",
    cmd: "openlvm results --compare run-1 run-2",
  },
  {
    label: "Start MCP server",
    cmd: "openlvm mcp serve --port 3847",
  },
  {
    label: "Red-team scan",
    cmd: "openlvm redteam swarm.yaml --plugins injection,discovery",
  },
];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded-md hover:bg-dark-surface transition-colors text-stone-gray hover:text-warm-silver"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-accent-emerald" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

export default function CLISection() {
  return (
    <section id="cli" className="relative py-24 lg:py-32 bg-near-black">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="inline-block px-3 py-1 mb-4 text-[12px] font-medium tracking-[0.5px] uppercase text-terracotta bg-brand-glow rounded-full">
            CLI
          </span>
          <h2 className="font-[family-name:var(--font-serif)] text-[clamp(2rem,4vw,3.25rem)] font-medium leading-[1.15] text-ivory mb-4">
            One command does
            <br />
            the whole flow
          </h2>
          <p className="text-[1.1rem] leading-[1.65] text-warm-silver max-w-[500px] mx-auto">
            Best-in-class CLI that feels like Promptfoo + DeepEval combined, with the VM power neither has.
          </p>
        </motion.div>

        {/* Command grid */}
        <div className="max-w-[800px] mx-auto">
          <div className="rounded-2xl overflow-hidden terminal-shadow bg-deep-dark">
            <div className="flex items-center gap-2 px-5 py-3 bg-dark-surface border-b border-border-dark">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-accent-coral-status/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-accent-amber/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-accent-emerald/60" />
              </div>
              <span className="text-[12px] text-stone-gray ml-2 font-[family-name:var(--font-mono)]">
                openlvm — CLI reference
              </span>
            </div>
            <div className="divide-y divide-border-dark">
              {commands.map((item, i) => (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, x: -12 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: i * 0.06 }}
                  className="flex items-center justify-between px-5 py-3.5 hover:bg-dark-surface/50 transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-stone-gray mb-1 font-medium uppercase tracking-[0.4px]">
                      {item.label}
                    </div>
                    <code className="text-[13px] text-coral font-[family-name:var(--font-mono)]">
                      $ {item.cmd}
                    </code>
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity ml-3">
                    <CopyButton text={item.cmd} />
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
