import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LegalPage } from "./LegalPage";
import type { LegalDocument, LegalSection } from "./types";

function rubriques(count: number): LegalSection[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `rubrique-${index + 1}`,
    title: `Rubrique ${index + 1}`,
    content: <p>Contenu {index + 1}</p>,
  }));
}

function documentDe(count: number): LegalDocument {
  return {
    title: "Politique de test",
    description: "Ce que dit ce texte.",
    updatedAt: "2026-10-01",
    sections: rubriques(count),
  };
}

describe("LegalPage (#333)", () => {
  it("rend le titre, la description et la date de dernière mise à jour", () => {
    render(<LegalPage document={documentDe(2)} />);
    expect(screen.getByRole("heading", { level: 1, name: "Politique de test" })).toBeInTheDocument();
    expect(screen.getByText("Ce que dit ce texte.")).toBeInTheDocument();
    const date = screen.getByText("1 octobre 2026");
    expect(date.tagName).toBe("TIME");
    expect(date).toHaveAttribute("dateTime", "2026-10-01");
    expect(date.parentElement).toHaveTextContent("Dernière mise à jour : 1 octobre 2026");
  });

  it("rend chaque rubrique sous un titre de niveau 2 portant son ancre", () => {
    render(<LegalPage document={documentDe(2)} />);
    const titre = screen.getByRole("heading", { level: 2, name: "Rubrique 2" });
    expect(titre.closest("[id]")).toHaveAttribute("id", "rubrique-2");
    expect(screen.getByText("Contenu 2")).toBeInTheDocument();
  });

  it("affiche un sommaire au-delà de quatre rubriques", () => {
    render(<LegalPage document={documentDe(5)} />);
    const sommaire = screen.getByRole("navigation", { name: "Sommaire" });
    expect(sommaire.querySelectorAll("a")).toHaveLength(5);
    expect(screen.getByRole("link", { name: "Rubrique 5" })).toHaveAttribute("href", "#rubrique-5");
  });

  it("n'affiche pas de sommaire à quatre rubriques ou moins", () => {
    render(<LegalPage document={documentDe(4)} />);
    expect(screen.queryByRole("navigation", { name: "Sommaire" })).not.toBeInTheDocument();
  });
});
