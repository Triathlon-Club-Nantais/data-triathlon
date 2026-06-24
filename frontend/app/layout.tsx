import type { Metadata } from "next";
import { Anton, Barlow, Barlow_Semi_Condensed } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { TcnTopbar } from "@/components/layout/TcnTopbar";
import { Toaster } from "@/components/ui/sonner";

// TCN Design System — Anton (titres/chiffres), Barlow (UI/corps),
// Barlow Semi Condensed (eyebrows, temps, tabulaires).
const anton = Anton({
  variable: "--font-anton",
  subsets: ["latin"],
  weight: "400",
  display: "swap",
});

const barlow = Barlow({
  variable: "--font-barlow",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
  display: "swap",
});

const barlowCond = Barlow_Semi_Condensed({
  variable: "--font-barlow-cond",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "TCN — Résultats triathlon",
  description: "Résultats de compétition des membres du Triathlon Club Nantais",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="fr"
      className={`${anton.variable} ${barlow.variable} ${barlowCond.variable}`}
    >
      <body
        className="min-h-screen text-foreground antialiased"
        style={{ background: "var(--tcn-paper)", fontFamily: "var(--tcn-font-body)" }}
      >
        <Providers>
          <TcnTopbar />
          <main className="min-h-[calc(100vh-73px)]">{children}</main>
          <Toaster richColors position="top-right" />
        </Providers>
      </body>
    </html>
  );
}
