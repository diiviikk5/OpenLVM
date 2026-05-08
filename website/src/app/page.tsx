"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Hls from "hls.js";
import { motion } from "framer-motion";

const HERO_VIDEO_SRC =
  "https://stream.mux.com/NcU3HlHeF7CUL86azTTzpy3Tlb00d6iF3BmCdFslMJYM.m3u8";
const CAPABILITIES_VIDEO_SRC =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260418_094631_d30ab262-45ee-4b7d-99f3-5d5848c8ef13.mp4";

const FADE_MS = 500;
const FADE_OUT_LEAD = 0.55;

function ArrowUpRightIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M7 17L17 7" />
      <path d="M7 7h10v10" />
    </svg>
  );
}

function PlayIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <polygon points="6 4 20 12 6 20 6 4" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v6l4 2" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a15 15 0 0 1 0 18" />
      <path d="M12 3a15 15 0 0 0 0 18" />
    </svg>
  );
}

function MaterialIcon({ path }: { path: string }) {
  return (
    <svg viewBox="0 -960 960 960" className="h-6 w-6 text-white" fill="currentColor" aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

function FadingVideo({ src, className, style }: { src: string; className?: string; style?: React.CSSProperties }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const fadingOutRef = useRef(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let hls: Hls | null = null;

    const setupSource = () => {
      if (src.endsWith(".m3u8") && Hls.isSupported()) {
        hls = new Hls();
        hls.loadSource(src);
        hls.attachMedia(video);
      } else {
        video.src = src;
      }
    };

    const cancelFade = () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    const fadeTo = (target: number, duration: number) => {
      cancelFade();
      const initial = Number.parseFloat(video.style.opacity || "0") || 0;
      const start = performance.now();
      const tick = (now: number) => {
        const progress = Math.min((now - start) / duration, 1);
        const value = initial + (target - initial) * progress;
        video.style.opacity = String(value);
        if (progress < 1) {
          rafRef.current = requestAnimationFrame(tick);
        } else {
          rafRef.current = null;
        }
      };
      rafRef.current = requestAnimationFrame(tick);
    };

    const onLoadedData = async () => {
      video.style.opacity = "0";
      try {
        await video.play();
      } catch {
        // no-op
      }
      fadeTo(1, FADE_MS);
    };

    const onTimeUpdate = () => {
      const { duration, currentTime } = video;
      const remaining = duration - currentTime;
      if (!fadingOutRef.current && Number.isFinite(remaining) && remaining <= FADE_OUT_LEAD && remaining > 0) {
        fadingOutRef.current = true;
        fadeTo(0, FADE_MS);
      }
    };

    const onEnded = async () => {
      video.style.opacity = "0";
      window.setTimeout(async () => {
        video.currentTime = 0;
        try {
          await video.play();
        } catch {
          // no-op
        }
        fadingOutRef.current = false;
        fadeTo(1, FADE_MS);
      }, 100);
    };

    setupSource();
    video.addEventListener("loadeddata", onLoadedData);
    video.addEventListener("timeupdate", onTimeUpdate);
    video.addEventListener("ended", onEnded);

    return () => {
      cancelFade();
      video.removeEventListener("loadeddata", onLoadedData);
      video.removeEventListener("timeupdate", onTimeUpdate);
      video.removeEventListener("ended", onEnded);
      if (hls) {
        hls.destroy();
      }
    };
  }, [src]);

  return (
    <video
      ref={videoRef}
      autoPlay
      muted
      playsInline
      preload="auto"
      className={className}
      style={{ opacity: 0, ...style }}
    />
  );
}

function BlurText({ text, className }: { text: string; className?: string }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLParagraphElement | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const words = useMemo(() => text.split(" "), [text]);

  return (
    <p ref={ref} className={className} style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", rowGap: "0.1em" }}>
      {words.map((word, i) => (
        <motion.span
          key={`${word}-${i}`}
          initial={{ filter: "blur(10px)", opacity: 0, y: 50 }}
          animate={
            visible
              ? {
                  filter: ["blur(10px)", "blur(5px)", "blur(0px)"],
                  opacity: [0, 0.5, 1],
                  y: [50, -5, 0],
                }
              : { filter: "blur(10px)", opacity: 0, y: 50 }
          }
          transition={{ duration: 0.7, times: [0, 0.5, 1], ease: "easeOut", delay: (i * 100) / 1000 }}
          style={{ display: "inline-block", marginRight: "0.28em" }}
        >
          {word}
        </motion.span>
      ))}
    </p>
  );
}

function HeroSection() {
  const navItems = [
    { label: "Home", href: "#hero" },
    { label: "Capabilities", href: "#capabilities" },
    { label: "Workbench", href: "/workbench" },
    { label: "Roadmap", href: "/roadmap" },
    { label: "GitHub", href: "https://github.com/diiviikk5/OpenLVM" },
  ];

  return (
    <section id="hero" className="relative min-h-screen bg-black overflow-hidden">
      <FadingVideo
        src={HERO_VIDEO_SRC}
        className="absolute left-1/2 top-0 -translate-x-1/2 object-cover object-top z-0"
        style={{ width: "120%", height: "120%" }}
      />

      <nav className="fixed top-4 left-0 right-0 z-50 px-8 lg:px-16">
        <div className="mx-auto max-w-[1320px] flex items-center justify-between">
          <div className="liquid-glass flex h-12 px-4 items-center justify-center rounded-full">
            <span className="font-heading italic text-white text-xl">OpenLVM</span>
          </div>

          <div className="hidden lg:flex items-center liquid-glass rounded-full px-1.5 py-1.5 gap-1.5">
            {navItems.map((item) => (
              <a key={item.label} href={item.href} className="px-3 py-2 text-sm font-medium text-white/90 font-body no-underline hover:text-white">
                {item.label}
              </a>
            ))}
            <a
              href="https://github.com/diiviikk5/OpenLVM#readme"
              target="_blank"
              rel="noreferrer"
              className="rounded-full bg-white text-black whitespace-nowrap px-4 py-2 text-sm font-medium flex items-center gap-2 no-underline hover:bg-white/90"
            >
              Launch Docs
              <ArrowUpRightIcon className="h-4 w-4" />
            </a>
          </div>

          <div className="h-12 w-12 opacity-0" />
        </div>
      </nav>

      <div className="relative z-10 min-h-screen flex flex-col pt-24 px-4">
        <div className="flex-1 flex flex-col items-center justify-center text-center">
          <motion.div
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut", delay: 0.4 }}
            className="liquid-glass rounded-full pl-1.5 pr-3 py-1.5 flex items-center gap-2"
          >
            <span className="bg-white text-black px-3 py-1 text-xs font-semibold rounded-full">OpenLVM</span>
            <span className="text-sm text-white/90">Shipping cinematic AI product visuals for modern commerce</span>
          </motion.div>

          <BlurText
            text="Build Product Visuals That Feel Impossible"
            className="mt-6 text-6xl md:text-7xl lg:text-[5.5rem] font-heading italic text-white leading-[0.8] max-w-2xl tracking-[-4px]"
          />

          <motion.p
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut", delay: 0.8 }}
            className="mt-4 text-sm md:text-base text-white max-w-2xl font-body font-light leading-tight"
          >
            OpenLVM turns plain product assets into premium launch-ready creatives with scene generation, batch styling, and physically accurate lighting in a single workflow.
          </motion.p>

          <motion.div
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut", delay: 1.1 }}
            className="flex items-center gap-6 mt-6"
          >
            <a href="/workbench" className="liquid-glass-strong rounded-full px-5 py-2.5 text-sm font-medium text-white flex items-center gap-2 no-underline hover:text-white">
              Open Workbench
              <ArrowUpRightIcon className="h-5 w-5" />
            </a>
            <a href="https://github.com/diiviikk5/OpenLVM" target="_blank" rel="noreferrer" className="text-white no-underline text-sm font-body flex items-center gap-2 hover:text-white/90">
              View Source
              <PlayIcon className="h-4 w-4" />
            </a>
          </motion.div>

          <motion.div
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: "easeOut", delay: 1.3 }}
            className="flex items-stretch gap-4 mt-8 flex-wrap justify-center"
          >
            <div className="liquid-glass rounded-[1.25rem] p-5 w-[220px]">
              <div className="h-7 w-7 border border-white/80 rounded-full flex items-center justify-center">
                <ClockIcon />
              </div>
              <p className="mt-6 font-heading italic text-white text-4xl tracking-[-1px] leading-none">12.4x</p>
              <p className="text-xs text-white font-body font-light mt-2">Faster campaign asset generation</p>
            </div>
            <div className="liquid-glass rounded-[1.25rem] p-5 w-[220px]">
              <div className="h-7 w-7 border border-white/80 rounded-full flex items-center justify-center">
                <GlobeIcon />
              </div>
              <p className="mt-6 font-heading italic text-white text-4xl tracking-[-1px] leading-none">280+</p>
              <p className="text-xs text-white font-body font-light mt-2">Brands and builders using OpenLVM</p>
            </div>
          </motion.div>
        </div>

        <motion.div
          initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
          animate={{ filter: "blur(0px)", opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut", delay: 1.4 }}
          className="flex flex-col items-center gap-4 pb-8"
        >
          <div className="liquid-glass rounded-full px-3.5 py-1 text-xs font-medium text-white">
            Trusted by teams launching products every week
          </div>
          <div className="flex items-center gap-12 md:gap-16 text-2xl md:text-3xl tracking-tight text-white font-heading italic flex-wrap justify-center">
            {"NovaCart PixelFoundry OrbitLab VelaStore Prisma".split(" ").map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

type Capability = {
  title: string;
  description: string;
  iconPath: string;
  tags: string[];
};

const CAPABILITIES: Capability[] = [
  {
    title: "AI Scene Engine",
    description:
      "OpenLVM understands your product and creates high-fidelity contextual environments that match your brand and campaign goals.",
    iconPath:
      "M5 21q-.825 0-1.412-.587T3 19V5q0-.825.588-1.412T5 3h14q.825 0 1.413.588T21 5v14q0 .825-.587 1.413T19 21H5Zm1-4h12l-3.75-5-3 4L9 13l-3 4Z",
    tags: ["Brand Context", "Photo Realism", "Infinite Scenes", "Campaign Ready"],
  },
  {
    title: "Batch Creative",
    description:
      "Generate full catalog sets in minutes with consistent styling, framing, and mood across your entire product line.",
    iconPath:
      "M4 6.47 5.76 10H20v8H4V6.47M22 4h-4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.89-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4Z",
    tags: ["Scale Fast", "Consistent Output", "Time Saver", "Publish Ready"],
  },
  {
    title: "Smart Lighting",
    description:
      "Automatic lighting and material adjustment. Achieve flawless integration with realistic shadows and sunlight.",
    iconPath:
      "M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1Zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7Z",
    tags: ["Ray Tracing", "Physical Shadows", "Studio Quality", "Sun Sync"],
  },
];

function CapabilitiesSection() {
  return (
    <section id="capabilities" className="relative min-h-screen bg-black overflow-hidden">
      <FadingVideo
        src={CAPABILITIES_VIDEO_SRC}
        className="absolute inset-0 w-full h-full object-cover z-0"
      />

      <div className="relative z-10 px-8 md:px-16 lg:px-20 pt-24 pb-10 flex flex-col min-h-screen">
        <div className="mb-auto">
          <motion.p
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            whileInView={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className="text-sm font-body text-white/80 mb-6"
          >
            // Capabilities
          </motion.p>
          <motion.h2
            initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
            whileInView={{ filter: "blur(0px)", opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.7, ease: "easeOut", delay: 0.1 }}
            className="font-heading italic text-white text-6xl md:text-7xl lg:text-[6rem] leading-[0.9] tracking-[-3px]"
          >
            OpenLVM
            <br />
            capabilities
          </motion.h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16">
            {CAPABILITIES.map((capability, idx) => (
              <motion.article
                key={capability.title}
                initial={{ filter: "blur(10px)", opacity: 0, y: 20 }}
                whileInView={{ filter: "blur(0px)", opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.7, ease: "easeOut", delay: 0.15 + idx * 0.12 }}
                className="liquid-glass rounded-[1.25rem] p-6 min-h-[360px] flex flex-col"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="liquid-glass h-11 w-11 rounded-[0.75rem] flex items-center justify-center">
                    <MaterialIcon path={capability.iconPath} />
                  </div>
                  <div className="flex flex-wrap justify-end gap-1.5 max-w-[70%]">
                    {capability.tags.map((tag) => (
                      <span key={tag} className="liquid-glass rounded-full px-3 py-1 text-[11px] text-white/90 font-body whitespace-nowrap">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex-1" />

                <div className="mt-6">
                  <h3 className="font-heading italic text-white text-3xl md:text-4xl tracking-[-1px] leading-none">{capability.title}</h3>
                  <p className="mt-3 text-sm text-white/90 font-body font-light leading-snug max-w-[32ch]">{capability.description}</p>
                </div>
              </motion.article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <main className="bg-black min-h-screen text-white">
      <HeroSection />
      <CapabilitiesSection />
    </main>
  );
}

