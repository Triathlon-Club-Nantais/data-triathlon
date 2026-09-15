import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GuideSection } from "./GuideSection";
import type { GuideSection as GuideSectionData } from "./types";

const section: GuideSectionData = {
  id: "club",
  titre: "Espace club",
  etapes: ["Ouvrir « Espace club » depuis la navigation.", "Consulter les podiums et la synthèse."],
  casUsage: "Voir où en est le club sur la saison en cours.",
  captures: [{ src: "/guide/membre/club.jpg", alt: "Espace club, synthèse et podiums" }],
};

describe("GuideSection", () => {
  it("rend le titre, les étapes, le cas d'usage et l'alt de chaque capture", () => {
    render(<GuideSection section={section} />);
    expect(screen.getByRole("heading", { name: "Espace club" })).toBeInTheDocument();
    expect(screen.getByText(section.etapes[0])).toBeInTheDocument();
    expect(screen.getByText(section.etapes[1])).toBeInTheDocument();
    expect(screen.getByText(section.casUsage)).toBeInTheDocument();
    expect(screen.getByAltText("Espace club, synthèse et podiums")).toBeInTheDocument();
  });

  it("pose l'id de la section comme ancre HTML", () => {
    const { container } = render(<GuideSection section={section} />);
    expect(container.querySelector("#club")).not.toBeNull();
  });

  it("rend une capture par entrée de `captures`", () => {
    const deux = { ...section, captures: [...section.captures, { src: "/guide/membre/club-2.png", alt: "Podiums détaillés" }] };
    render(<GuideSection section={deux} />);
    expect(screen.getAllByRole("img")).toHaveLength(2);
  });
});

describe("GuideSection — accès direct par ancre (#865, US3)", () => {
  it("réserve un scroll-margin-top pour ne pas masquer l'ancre sous la nav fixe", () => {
    const { container } = render(<GuideSection section={section} />);
    const cible = container.querySelector("#club") as HTMLElement;
    expect(cible.style.scrollMarginTop).not.toBe("");
  });
});

describe("GuideSection — capture placeholder (#865, #874)", () => {
  const avecPlaceholder: GuideSectionData = {
    ...section,
    captures: [{ src: "/guide/admin/epreuves.jpg", alt: "Écran de gestion des épreuves", placeholder: true }],
  };

  it("le dit dans l'alt, pas seulement visuellement — un lecteur d'écran n'a que le texte alternatif", () => {
    render(<GuideSection section={avecPlaceholder} />);
    expect(screen.getByAltText("Capture à venir — Écran de gestion des épreuves")).toBeInTheDocument();
  });

  it("affiche un badge visuel « Capture à venir »", () => {
    render(<GuideSection section={avecPlaceholder} />);
    expect(screen.getByText("Capture à venir")).toBeInTheDocument();
  });

  it("ne modifie pas l'alt d'une capture réelle", () => {
    render(<GuideSection section={section} />);
    expect(screen.getByAltText("Espace club, synthèse et podiums")).toBeInTheDocument();
    expect(screen.queryByText("Capture à venir")).not.toBeInTheDocument();
  });
});
