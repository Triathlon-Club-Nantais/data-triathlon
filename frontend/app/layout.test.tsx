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

import RootLayout from "./layout";

describe("RootLayout — lien d'évitement (A11Y-1)", () => {
  it("propose un lien « Aller au contenu » qui cible le <main>", () => {
    render(<RootLayout>{<p>contenu de la page</p>}</RootLayout>);

    const lien = screen.getByRole("link", { name: "Aller au contenu" });
    expect(lien).toHaveAttribute("href", "#contenu");

    const main = document.querySelector("main");
    expect(main).toHaveAttribute("id", "contenu");
  });
});
