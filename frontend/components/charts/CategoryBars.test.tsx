import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CategoryBars } from "./CategoryBars";

describe("CategoryBars", () => {
  it("affiche une barre par catégorie", () => {
    render(
      <CategoryBars
        categories={[
          { name: "S1", count: 284 },
          { name: "S2", count: 216 },
        ]}
        total={1000}
      />,
    );
    expect(screen.getAllByText(/^S[12]$/).length).toBe(2);
  });

  it("rapporte chaque barre au total fourni, pas à la somme des catégories affichées", () => {
    // 284/1000 = 28,4 % ; les rapporter aux 500 affichés donnerait 56,8 %.
    render(<CategoryBars categories={[{ name: "S1", count: 284 }]} total={1000} />);
    expect(screen.getByText("28,4%")).toBeInTheDocument();
  });

  it("affiche un état vide quand aucune catégorie n'est renseignée", () => {
    render(<CategoryBars categories={[]} total={0} />);
    expect(screen.getByText("Catégories non renseignées")).toBeInTheDocument();
  });

  it("n'échoue pas quand le total est nul", () => {
    const { container } = render(
      <CategoryBars categories={[{ name: "S1", count: 0 }]} total={0} />,
    );
    expect(container.textContent).not.toContain("NaN");
    expect(screen.getByText("0,0%")).toBeInTheDocument();
  });

  it("donne une couleur distincte à chaque catégorie", () => {
    const { container } = render(
      <CategoryBars
        categories={[
          { name: "S1", count: 1 },
          { name: "S2", count: 1 },
        ]}
        total={2}
      />,
    );
    const fills = [...container.querySelectorAll("[style*='border-radius: 999px'] > div")].map(
      (bar) => (bar as HTMLElement).style.background,
    );
    expect(fills[0]).not.toBe(fills[1]);
  });

  it("récapitule la répartition pour un lecteur d'écran", () => {
    render(
      <CategoryBars
        categories={[
          { name: "V1", count: 30 },
          { name: "S", count: 20 },
        ]}
        total={100}
      />,
    );
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Répartition par catégorie : V1 30,0 %, S 20,0 %, Autres 50,0 %.",
    );
  });

  // ── Ce que la carte omet (#486, RES-7) ───────────────────────────────────
  //
  // Sur la course 27 de la base de dev, les huit barres affichées ne couvrent
  // que 70,1 % des participants : 29,9 % n'apparaissaient nulle part, et rien
  // ne le disait. L'audit relevait déjà 86,1 % sur la course 214.

  it("ajoute une barre « Autres » pour la part que les catégories affichées ne couvrent pas", () => {
    render(
      <CategoryBars
        categories={[
          { name: "S1", count: 284 },
          { name: "S2", count: 216 },
        ]}
        total={1000}
      />,
    );

    expect(screen.getByText("Autres (500)")).toBeInTheDocument();
    expect(screen.getByText("50,0%")).toBeInTheDocument();
  });

  it("fait sommer les barres à 100 % du dénominateur publié", () => {
    render(
      <CategoryBars
        categories={[
          { name: "S1", count: 60 },
          { name: "S2", count: 30 },
        ]}
        total={100}
      />,
    );

    const parts = screen
      .getAllByText(/^\d+,\d%$/)
      .map((el) => Number(el.textContent!.replace(",", ".").replaceAll("%", "")));
    expect(parts.reduce((a, b) => a + b, 0)).toBeCloseTo(100, 1);
  });

  it("n'ajoute aucune barre « Autres » quand le reste est nul", () => {
    render(
      <CategoryBars
        categories={[
          { name: "S1", count: 60 },
          { name: "S2", count: 40 },
        ]}
        total={100}
      />,
    );

    expect(screen.queryByText(/^Autres/)).not.toBeInTheDocument();
  });

  it("n'ajoute aucune barre « Autres » quand le dénominateur est incohérent", () => {
    // Un reste négatif ne se dessine pas : mieux vaut ne rien dire que mentir
    // dans l'autre sens.
    render(<CategoryBars categories={[{ name: "S1", count: 120 }]} total={100} />);

    expect(screen.queryByText(/^Autres/)).not.toBeInTheDocument();
  });

  // ── Des barres qui mènent quelque part (#486, RES-11) ────────────────────

  it("rend chaque barre activable vers le classement filtré quand un lien est fourni", () => {
    render(
      <CategoryBars
        categories={[{ name: "V2", count: 120 }]}
        total={1000}
        hrefFor={(name) => `/courses/1?category=${name}`}
      />,
    );

    expect(screen.getByRole("link", { name: /V2/ })).toHaveAttribute(
      "href",
      "/courses/1?category=V2",
    );
  });

  it("porte le libellé complet dans le nom du lien — au clavier comme au doigt", () => {
    // Une infobulle de survol n'existe ni pour l'un ni pour l'autre (FR-028).
    render(
      <CategoryBars
        categories={[{ name: "PoM", count: 34 }]}
        total={100}
        hrefFor={() => "/x"}
      />,
    );

    const lien = screen.getByRole("link");
    expect(lien).toHaveAccessibleName(/PoM — Poussin, hommes/);
    expect(lien).toHaveAttribute("title", "PoM — Poussin, hommes");
  });

  it("rend le code tel quel quand la table ne le connaît pas", () => {
    render(
      <CategoryBars categories={[{ name: "ZZZ9", count: 10 }]} total={100} hrefFor={() => "/x"} />,
    );

    expect(screen.getByRole("link")).toHaveAttribute("title", "ZZZ9");
  });

  it("ne rend jamais la barre « Autres » activable", () => {
    // « Autres » n'est pas une catégorie : aucun filtre ne saurait la reproduire.
    render(
      <CategoryBars
        categories={[{ name: "S1", count: 40 }]}
        total={100}
        hrefFor={(name) => `/courses/1?category=${name}`}
      />,
    );

    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByText("Autres (60)")).toBeInTheDocument();
  });

  it("reste une image quand aucun lien n'est fourni", () => {
    render(<CategoryBars categories={[{ name: "S1", count: 100 }]} total={100} />);

    expect(screen.getByRole("img")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
