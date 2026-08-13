import type { Metadata } from "next";
import { Anton, Barlow, Barlow_Semi_Condensed } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { AppNav } from "@/components/layout/AppNav";
import { VersionFooter } from "@/components/layout/VersionFooter";
import { Toaster } from "@/components/ui/sonner";
import { FeedbackButton } from "@/components/tcn/FeedbackButton";
import { CLUB_NAME } from "@/lib/club";

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
  description: `Résultats de compétition des membres du ${CLUB_NAME}`,
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
          {/* Colonne sous md (barre + contenu), rangée au-dessus (rail +
              contenu) : la nav prend la hauteur, le contenu prend le reste.
              `VersionFooter` vit sous le **contenu**, pas sous le rail. */}
          <div className="flex min-h-screen flex-col md:flex-row">
            <AppNav />
            <div className="flex min-w-0 flex-1 flex-col">
              <main className="flex-1">{children}</main>
              <VersionFooter />
            </div>
          </div>
          <Toaster richColors position="top-right" />
          <FeedbackButton />
        </Providers>
      </body>
    </html>
  );
}
