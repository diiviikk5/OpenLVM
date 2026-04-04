import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "OpenLVM — Agent-Native VM & Testing Framework",
  description:
    "The performance-first agent-native virtual machine with built-in testing, observability, chaos simulation, and deterministic replay. Fork. Test. Ship.",
  keywords: [
    "agent VM",
    "LLM testing",
    "multi-agent",
    "copy-on-write",
    "AI sandbox",
    "eval framework",
    "MCP",
    "observability",
  ],
  openGraph: {
    title: "OpenLVM — Agent-Native VM & Testing Framework",
    description:
      "Fork 5000 parallel agent worlds in <5ms. Test with DeepEval + Promptfoo. Observe with OpenTelemetry. Ship with confidence.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-[family-name:var(--font-inter)] bg-near-black text-ivory">
        {children}
      </body>
    </html>
  );
}
