"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Zap } from "lucide-react";
import { GithubIcon } from "./icons";
import Link from "next/link";

const navLinks = [
  { label: "Features", href: "#features" },
  { label: "How It Works", href: "#how-it-works" },
  { label: "Architecture", href: "#architecture" },
  { label: "Workbench", href: "/workbench" },
  { label: "CLI", href: "#cli" },
  { label: "Comparison", href: "#comparison" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.header
      initial={{ y: -80 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? "glass-dark shadow-[0_1px_0_0_rgba(48,48,46,0.6)]"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-[1200px] mx-auto px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-terracotta flex items-center justify-center shadow-[0_0_0_1px_rgba(201,100,66,0.4)]">
            <Zap className="w-4.5 h-4.5 text-ivory" strokeWidth={2.5} />
          </div>
          <span className="font-[family-name:var(--font-serif)] text-xl font-medium text-ivory tracking-tight">
            Open<span className="text-terracotta">LVM</span>
          </span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="px-3.5 py-2 text-[15px] text-warm-silver hover:text-ivory transition-colors duration-200 rounded-lg hover:bg-dark-surface/50"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Desktop CTA */}
        <div className="hidden md:flex items-center gap-3">
          <Link
            href="https://github.com/diiviikk5/OpenLVM"
            target="_blank"
            className="flex items-center gap-2 px-3.5 py-2 text-[14px] font-medium text-warm-silver hover:text-ivory rounded-xl border border-border-dark hover:border-olive-gray transition-all duration-200 hover:shadow-[0_0_0_1px_rgba(48,48,46,0.8)]"
          >
            <GithubIcon className="w-4 h-4" />
            Star
          </Link>
          <Link
            href="#quickstart"
            className="flex items-center gap-2 px-4 py-2 text-[14px] font-medium text-ivory bg-terracotta rounded-xl hover:bg-coral transition-all duration-200 shadow-[0_0_0_1px_rgba(201,100,66,0.4)]"
          >
            Get Started
          </Link>
        </div>

        {/* Mobile toggle */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden p-2 rounded-lg text-warm-silver hover:bg-dark-surface/50"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden glass-dark border-t border-border-dark"
          >
            <div className="px-6 py-4 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="block px-3 py-2.5 text-[15px] text-warm-silver hover:text-ivory rounded-lg hover:bg-dark-surface/50 transition-colors"
                >
                  {link.label}
                </Link>
              ))}
              <div className="pt-3 border-t border-border-dark mt-2">
                <Link
                  href="#quickstart"
                  className="block text-center px-4 py-2.5 text-[14px] font-medium text-ivory bg-terracotta rounded-xl"
                >
                  Get Started
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
