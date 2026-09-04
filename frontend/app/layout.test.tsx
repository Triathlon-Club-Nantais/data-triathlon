import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// `next/font/google` normalise ses polices via un plugin de build (fetch des
// fichiers, génération de `variable`) absent de l'environnement de test.
vi.mock("next/font/google", () => {
  const police = () => ({ variable: "mock-font" });
  return { Anton: police, Barlow: police, Barlow_Semi_Condensed: police };
});

// RootLayout compose la coquille entière (nav, footer, toasts, bouton de
// retour) : sans rapport avec ce qui est testé ici (lien d'évitement + cible
// de `<main>`), et chacun a ses propres tests.
vi.mock("@/components/layout/AppNav", () => ({ AppNav: () => null }));
vi.mock("@/components/layout/VersionFooter", () => ({ VersionFooter: () => null }));
vi.mock("@/components/ui/sonner", () => ({ Toaster: () => null }));
vi.mock("@/components/tcn/FeedbackButton", () => ({ FeedbackButton: () => null }));
vi.mock("./providers", () => ({ Providers: ({ children }: { children: React.ReactNode }) => children }));

// `connection()` n'a de sens que dans une requête Next ; hors serveur il lève.
vi.mock("next/server", () => ({ connection: async () => {} }));

// `cookies()` lève hors d'une requête Next (#482, NAV-3) ; ce test ne porte
// pas sur la largeur du rail, donc un jar vide (comportement replié par défaut).
//
// `headers()` sert au nonce relu pour Base UI (#570) ; `POLITIQUE` est
// réaffectée par les tests qui portent dessus.
let POLITIQUE: string | null = null;
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: () => undefined }),
  headers: async () => ({
    get: (nom: string) => (nom === "content-security-policy" ? POLITIQUE : null),
  }),
}));

// `CSPProvider` n'est mocké que pour observer le nonce qu'il reçoit : c'est le
// seul effet du layout à vérifier ici, le reste appartient à Base UI.
let NONCE_RECU: string | undefined;
vi.mock("@base-ui/react/csp-provider", () => ({
  CSPProvider: ({ nonce, children }: { nonce?: string; children: React.ReactNode }) => {
    NONCE_RECU = nonce;
    return children;
  },
}));

import RootLayout from "./layout";

describe("RootLayout — lien d'évitement (A11Y-1)", () => {
  it("propose un lien « Aller au contenu » qui cible le <main>", async () => {
    // RootLayout est un composant serveur `async` : on l'attend avant de rendre.
    render(await RootLayout({ children: <p>contenu de la page</p> }));

    const lien = screen.getByRole("link", { name: "Aller au contenu" });
    expect(lien).toHaveAttribute("href", "#contenu");

    const main = document.querySelector("main");
    expect(main).toHaveAttribute("id", "contenu");
  });
});

describe("RootLayout — espace réservé sous le contenu mobile (#482, NAV-4)", () => {
  it("réserve la hauteur de la barre basse mobile sous <main>, seulement sous md", async () => {
    render(await RootLayout({ children: <p>contenu de la page</p> }));

    const conteneur = document.querySelector("main")?.parentElement;
    expect(conteneur?.className).toContain("pb-[var(--tcn-nav-bottom)]");
    expect(conteneur?.className).toContain("md:pb-0");
  });
});

describe("RootLayout — nonce transmis à Base UI (#570)", () => {
  it("extrait le nonce de la politique et le passe à CSPProvider", async () => {
    // Sans lui, le `<style>` que Base UI injecte au montage d'un popup
    // (`.base-ui-disable-scrollbar`) serait bloqué : barres de défilement
    // réapparues sous chaque sélecteur.
    POLITIQUE = "default-src 'self'; script-src 'self' 'nonce-abc123' 'strict-dynamic'";

    render(await RootLayout({ children: <p>contenu de la page</p> }));

    expect(NONCE_RECU).toBe("abc123");
  });

  it("ne passe rien quand aucune politique n'est posée", async () => {
    // Le rendu ne doit pas dépendre de la CSP : sans en-tête, Base UI retombe
    // sur son comportement par défaut plutôt que de casser la page.
    POLITIQUE = null;
    NONCE_RECU = "residu";

    render(await RootLayout({ children: <p>contenu de la page</p> }));

    expect(NONCE_RECU).toBeUndefined();
  });
});
