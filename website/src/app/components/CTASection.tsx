"use client";

import { motion } from "framer-motion";
import { Terminal, ArrowRight, Zap } from "lucide-react";
import { GithubIcon } from "./icons";
import Link from "next/link";

export default function CTASection() {
  return (
    <section id="quickstart" className="relative py-24 lg:py-32 overflow-hidden bg-near-black">
      {/* Background glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] rounded-full bg-brand-glow blur-[160px] opacity-40" />
      </div>

      <div className="relative max-w-[800px] mx-auto px-6 lg:px-8 text-center">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
        >
          <div className="w-14 h-14 rounded-2xl bg-terracotta flex items-center justify-center mx-auto mb-8 shadow-[0_0_40px_rgba(201,100,66,0.3)]">
            <Zap className="w-7 h-7 text-ivory" />
          </div>

          <h2 className="font-[family-name:var(--font-serif)] text-[clamp(2rem,4vw,3.25rem)] font-medium leading-[1.15] text-ivory mb-4">
            Ready to ship agents
            <br />
            that actually work?
          </h2>
          <p className="text-[1.1rem] leading-[1.65] text-warm-silver max-w-[480px] mx-auto mb-10">
            Stop burning tokens on untested swarms. Start forking, testing, and shipping with confidence.
          </p>

          {/* Install command */}
          <div className="inline-flex items-center gap-3 px-5 py-3.5 rounded-2xl bg-dark-surface text-warm-silver font-[family-name:var(--font-mono)] text-[15px] mb-8 shadow-[0_0_0_1px_rgba(48,48,46,0.8)] border border-border-dark hover:shadow-[0_0_24px_rgba(201,100,66,0.15)] transition-shadow">
            <Terminal className="w-4.5 h-4.5 text-coral" />
            <span>pip install openlvm</span>
          </div>

          {/* CTAs */}
          <div className="flex flex-wrap justify-center gap-3.5">
            <Link
              href="/workbench"
              className="group inline-flex items-center gap-2 px-6 py-3 text-[15px] font-medium text-ivory bg-terracotta rounded-xl hover:bg-coral transition-all duration-300 shadow-[0_0_0_1px_rgba(201,100,66,0.4)] hover:shadow-[0_0_24px_rgba(201,100,66,0.3)]"
            >
              Open Workbench
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="https://github.com/diiviikk5/OpenLVM"
              target="_blank"
              className="group inline-flex items-center gap-2 px-6 py-3 text-[15px] font-medium text-warm-silver bg-dark-surface rounded-xl hover:bg-olive-gray/20 transition-all duration-200 shadow-[0_0_0_1px_rgba(48,48,46,0.8)] border border-border-dark"
            >
              <GithubIcon className="w-4.5 h-4.5" />
              Star on GitHub
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
