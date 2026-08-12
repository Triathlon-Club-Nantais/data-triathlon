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

  it("écrit la variante hero en encre sur le dégradé orange", () => {
    // #299 : le libellé à 13 px et la pastille de delta étaient en blanc sur
    // dégradé (3,68:1 à l'extrémité foncée) ; seule la valeur à 86 px tenait le
    // seuil « texte large ». L'encre les met les trois à 4,54:1 au pire.
    render(<StatCard variant="hero" label="Dossards" value={120} delta="12 athlètes" />);

    for (const texte of ["Dossards", "120", "12 athlètes"]) {
      expect(screen.getByText(texte)).toHaveStyle({ color: "var(--tcn-ink)" });
    }
  });
});
