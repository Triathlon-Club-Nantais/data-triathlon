import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("affiche la sous-ligne quand un hint est fourni", () => {
    render(<StatCard label="Meilleur ratio" value="Top 14%" hint="42e sur 300" />);

    expect(screen.getByText("Top 14%")).toBeInTheDocument();
    expect(screen.getByText("42e sur 300")).toBeInTheDocument();
  });

  it("n'affiche aucune sous-ligne sans hint", () => {
    render(<StatCard label="Top 10" value={3} />);

    expect(screen.queryByTestId("statcard-hint")).not.toBeInTheDocument();
  });

  it("affiche le delta sur la variante standard", () => {
    render(<StatCard label="Podiums" value={22} delta="scratch, genre ou catégorie" />);
    expect(screen.getByText("scratch, genre ou catégorie")).toBeInTheDocument();
  });

  it("affiche le delta sur la variante hero", () => {
    render(<StatCard variant="hero" label="Dossards" value={120} delta="12 athlètes" />);
    expect(screen.getByText("12 athlètes")).toBeInTheDocument();
  });

  it("écrit la variante hero en blanc plein sur le dégradé orange", () => {
    // #299 : le libellé de 13px n'était qu'à 85 % d'opacité et la pastille de
    // delta sur un voile blanc, soit 3,68 et 3,42:1 ; seule la valeur de 86px
    // tenait son seuil de grand texte. Le blanc reste — c'est le dégradé qui a
    // été assombri, et la pastille qui assombrit désormais son fond.
    render(<StatCard variant="hero" label="Dossards" value={120} delta="12 athlètes" />);

    for (const texte of ["Dossards", "120", "12 athlètes"]) {
      expect(screen.getByText(texte)).toHaveStyle({ color: "#fff" });
    }
    expect(screen.getByText("12 athlètes")).toHaveStyle({ background: "rgba(0,0,0,.12)" });
  });

  it("répartit le contenu de la variante hero en colonne flex quand la carte est étirée (#688)", () => {
    // La grille du tableau de bord peut faire de cette carte le voisin de
    // colonnes plus hautes : sans `flex`, le contenu restait empilé en haut
    // du `block`, laissant un vide en bas. `value` doit pouvoir grandir pour
    // occuper l'espace disponible, et la pastille ne doit pas être étirée en
    // largeur par le `stretch` par défaut de l'axe transverse.
    render(<StatCard variant="hero" label="Dossards" value={120} delta="12 athlètes" />);

    expect(screen.getByText("Dossards").parentElement).toHaveStyle({ display: "flex", flexDirection: "column" });
    expect(screen.getByText("120")).toHaveStyle({ flex: "1 1 auto" });
    expect(screen.getByText("12 athlètes")).toHaveStyle({ alignSelf: "flex-start" });
  });

  it("keeps the hero value at 86 px", () => {
    render(<StatCard variant="hero" label="Résultats" value="12 345" />);
    expect(screen.getByText("12 345")).toHaveStyle({ fontSize: "86px" });
  });

  describe("value wider than its tile (#1540)", () => {
    // 179 px de carte, soit 131 px utiles hors rembourrage (2 x 24 px) : la
    // tuile Top 10 du tableau de bord à 640 px, le cas le plus étroit mesuré.
    const AVAILABLE = 131;
    // jsdom ne mesure rien. Largeur simulée calée sur Anton : « F 123 H 145 »
    // fait 227 px à 68 px, dont environ 49 px de libellés F / H et de marges
    // qui ne suivent pas la police.
    let fixedPx = 0;
    const width = (el: Element) => {
      const size = parseFloat((el as HTMLElement).style.fontSize);
      const chars = (el.textContent ?? "").length;
      return Math.round(fixedPx + size * chars * ((227 - fixedPx) / 68 / 11));
    };

    beforeEach(() => {
      fixedPx = 0;
      vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(AVAILABLE + 48);
      vi.spyOn(Element.prototype, "scrollWidth", "get").mockImplementation(function (this: Element) {
        return this.classList.contains("tcn-stat-value") ? width(this) : 0;
      });
    });
    afterEach(() => vi.restoreAllMocks());

    it("shrinks a value that would overflow until it fits the tile", () => {
      render(<StatCard label="Top 10" value="F 123 H 145" />);

      const value = screen.getByText("F 123 H 145");
      expect(parseFloat(value.style.fontSize)).toBeLessThan(68);
      expect(width(value)).toBeLessThanOrEqual(AVAILABLE);
    });

    it("still fits when part of the value does not scale with the font size", () => {
      fixedPx = 49;
      render(<StatCard label="Top 10" value="F 123 H 145" />);

      expect(width(screen.getByText("F 123 H 145"))).toBeLessThanOrEqual(AVAILABLE);
    });

    it("keeps the 68 px size when the value fits", () => {
      render(<StatCard label="Top 10" value={42} />);
      expect(screen.getByText("42")).toHaveStyle({ fontSize: "68px" });
    });

    it("starts from the caller's valueFontSize", () => {
      render(<StatCard label="Temps" value="2h05" valueFontSize={40} />);
      expect(screen.getByText("2h05")).toHaveStyle({ fontSize: "40px" });
    });
  });
});
