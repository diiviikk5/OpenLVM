import type { Metadata } from "next";
import { Barlow, Instrument_Serif } from "next/font/google";
import "./globals.css";

const barlow = Barlow({
  variable: "--font-barlow",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  display: "swap",
});

const instrument = Instrument_Serif({
  variable: "--font-instrument",
  weight: "400",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "OpenLVM",
  description:
    "OpenLVM landing experience with cinematic motion backgrounds, liquid-glass UI, and product-visual AI storytelling.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${barlow.variable} ${instrument.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-body bg-black text-white">
        {children}
      </body>
    </html>
  );
}

