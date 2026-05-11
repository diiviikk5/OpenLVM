"use client";

import { Zap, ExternalLink } from "lucide-react";
import { GithubIcon } from "./icons";
import Link from "next/link";

const footerLinks = {
  Product: [
    { label: "Features", href: "/#capabilities" },
    { label: "Architecture", href: "/solana" },
    { label: "CLI Reference", href: "https://github.com/diiviikk5/OpenLVM#current-commands" },
    { label: "Comparison", href: "/workbench#compare-results" },
  ],
  Resources: [
    { label: "Documentation", href: "https://github.com/diiviikk5/OpenLVM#readme" },
    { label: "Quickstart", href: "/workbench#quick-run" },
    { label: "Examples", href: "https://github.com/diiviikk5/OpenLVM/tree/master/examples" },
    { label: "Changelog", href: "https://github.com/diiviikk5/OpenLVM/commits/master" },
  ],
  Community: [
    { label: "GitHub", href: "https://github.com/diiviikk5/OpenLVM" },
    { label: "Discussions", href: "https://github.com/diiviikk5/OpenLVM/discussions" },
    { label: "Issues", href: "https://github.com/diiviikk5/OpenLVM/issues" },
    { label: "Contributing", href: "https://github.com/diiviikk5/OpenLVM/pulls" },
  ],
};

export default function Footer() {
  return (
    <footer className="border-t border-border-dark bg-dark-surface py-16">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
          {/* Brand column */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-terracotta flex items-center justify-center">
                <Zap className="w-3.5 h-3.5 text-ivory" strokeWidth={2.5} />
              </div>
              <span className="font-[family-name:var(--font-serif)] text-lg font-medium text-ivory">
                Open<span className="text-terracotta">LVM</span>
              </span>
            </Link>
            <p className="text-[14px] leading-[1.6] text-warm-silver max-w-[240px] mb-4">
              The agent-native VM with built-in testing, observability, and chaos simulation.
            </p>
            <div className="flex gap-2">
              <Link
                href="https://github.com/diiviikk5/OpenLVM"
                target="_blank"
                className="p-2 rounded-lg text-stone-gray hover:text-ivory hover:bg-near-black transition-colors"
              >
                <GithubIcon className="w-4 h-4" />
              </Link>
              <Link
                href="https://github.com/diiviikk5/OpenLVM#readme"
                className="p-2 rounded-lg text-stone-gray hover:text-ivory hover:bg-near-black transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
              </Link>
            </div>
          </div>

          {/* Link columns */}
          {Object.entries(footerLinks).map(([title, links]) => (
            <div key={title}>
              <h4 className="text-[13px] font-semibold text-ivory mb-3 uppercase tracking-[0.3px]">
                {title}
              </h4>
              <ul className="space-y-2">
                {links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-[14px] text-warm-silver hover:text-ivory transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom */}
        <div className="pt-8 border-t border-border-dark flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-[13px] text-stone-gray">
            © {new Date().getFullYear()} OpenLVM Contributors. Apache 2.0 License.
          </p>
          <div className="flex items-center gap-1.5 text-[12px] text-stone-gray">
            <span>Built with</span>
            <span className="font-semibold text-terracotta">Zig</span>
            <span>+</span>
            <span className="font-semibold text-accent-amber">Python</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
