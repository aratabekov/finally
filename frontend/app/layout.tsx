import type { Metadata } from "next";
import { IBM_Plex_Mono, Archivo } from "next/font/google";
import "./globals.css";

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FinAlly Terminal",
  description: "AI trading workstation with live market data and an LLM copilot",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${plexMono.variable} ${archivo.variable}`}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
