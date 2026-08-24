import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BarList } from "./BarList";

const SPREAD: [string, number][] = [
  ["a", 279],
  ["b", 40],
  ["c", 1],
];

describe("BarList", () => {
  it("garde une barre visible sur deux ordres de grandeur", () => {
    // 1 sur un maximum de 279 vaut 0,36 % : la barre disparaissait. Le plancher
    // la rend visible sans toucher à l'échelle — la valeur exacte reste écrite
    // à droite, c'est elle qui porte la comparaison fine.
    const { container } = render(<BarList entries={SPREAD} labeller={(k) => k} />);
    const bars = [...container.querySelectorAll("[data-bar]")] as HTMLElement[];
    expect(bars[0].style.width).toBe("100%");
    expect(parseFloat(bars[2].style.width)).toBeGreaterThanOrEqual(2);
  });

  it("reste strictement linéaire entre deux valeurs au-dessus du plancher", () => {
    const { container } = render(
      <BarList entries={[["a", 100], ["b", 50]]} labeller={(k) => k} />,
    );
    const bars = [...container.querySelectorAll("[data-bar]")] as HTMLElement[];
    expect(bars[1].style.width).toBe("50%");
  });

  it("récapitule la répartition pour un lecteur d'écran, sans vocabulaire de structure de données (#480)", () => {
    // « Répartition sur N entrées » nommait la boîte, pas ce qu'elle contient.
    // Sans indication de l'appelant, le récapitulatif reste honnête et se
    // limite à ce que le composant sait réellement.
    render(<BarList entries={SPREAD} labeller={(k) => k.toUpperCase()} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Répartition : A 279, B 40, C 1.",
    );
  });

  it("nomme l'objet de la répartition quand l'appelant le fournit (#480)", () => {
    render(
      <BarList
        entries={SPREAD}
        labeller={(k) => k.toUpperCase()}
        subjectLabel="type d'épreuve"
      />,
    );
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Répartition par type d'épreuve : A 279, B 40, C 1.",
    );
  });

  it("rend l'état vide sans récapitulatif", () => {
    render(<BarList entries={[]} labeller={(k) => k} emptyTitle="Aucune donnée" />);
    expect(screen.getByText("Aucune donnée")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });
});
