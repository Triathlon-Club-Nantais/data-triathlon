import { describe, it, expect } from "vitest";
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
});
