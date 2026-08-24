import type { Metadata } from "next";
import { cookies } from "next/headers";
import { connection } from "next/server";
import { Anton, Barlow, Barlow_Semi_Condensed } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { AppNav } from "@/components/layout/AppNav";
import { VersionFooter } from "@/components/layout/VersionFooter";
import { Toaster } from "@/components/ui/sonner";
import { FeedbackButton } from "@/components/tcn/FeedbackButton";
import { CLUB_NAME } from "@/lib/club";
import { NAV_WIDTH_COOKIE } from "@/lib/nav-cookies";

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

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Rendu dynamique de **toutes** les routes (#448) : un nonce n'existe qu'à la
  // requête, donc une page générée au build livrerait des scripts sans nonce —
  // rapportés à tort en violation, et cassés le jour du mode bloquant. Le
  // layout racine s'appliquant à tout, cet unique `await` suffit.
  //
  // Pas `export const dynamic = "force-dynamic"` : la doc le décrit comme
  // équivalent à `{ cache: "no-store", next: { revalidate: 0 } }` sur **chaque**
  // `fetch`, ce qui annulerait le cache de #352. `connection()` n'attend que la
  // requête et ne touche pas au Data Cache.
  await connection();

  // Largeur du rail décidée avant la peinture (#482, NAV-3) : le cookie que
  // `AppNav` écrit au pliage/dépliage (`document.cookie`, jamais relayé à
  // l'API) est relu ici pour que le rendu serveur et la première passe
  // client partagent déjà la bonne largeur — plus de bascule 76 px → 288 px
  // après coup.
  const jar = await cookies();
  const initialExpanded = jar.get(NAV_WIDTH_COOKIE)?.value === "1";

  return (
    <html
      lang="fr"
      className={`${anton.variable} ${barlow.variable} ${barlowCond.variable}`}
    >
      <body
        className="min-h-screen text-foreground antialiased"
        style={{ background: "var(--tcn-paper)", fontFamily: "var(--tcn-font-body)" }}
      >
        <a
          href="#contenu"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-[var(--tcn-orange)] focus:px-4 focus:py-2 focus:text-white"
        >
          Aller au contenu
        </a>
        <Providers>
          {/* Colonne sous md (barre + contenu), rangée au-dessus (rail +
              contenu) : la nav prend la hauteur, le contenu prend le reste.
              `VersionFooter` vit sous le **contenu**, pas sous le rail. */}
          <div className="flex min-h-screen flex-col md:flex-row">
            <AppNav initialExpanded={initialExpanded} />
            <div className="flex min-w-0 flex-1 flex-col pb-[var(--tcn-nav-bottom)] md:pb-0">
              <main id="contenu" tabIndex={-1} className="flex-1">
                {children}
              </main>
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
