import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RankingEvolutionStep } from "@/lib/types";
import { RankingEvolutionChart } from "./RankingEvolutionChart";

const STEPS: RankingEvolutionStep[] = [
  { segment: "swim", scratch_position: 91, segment_position: 88 },
  { segment: "t1", scratch_position: 91, segment_position: 112 },
  { segment: "bike", scratch_position: 74, segment_position: 68 },
  { segment: "t2", scratch_position: 63, segment_position: 60 },
  { segment: "run", scratch_position: 56, segment_position: 63 },
];

function renderChart(steps = STEPS) {
  return render(<RankingEvolutionChart steps={steps} eventType="triathlon-m" />);
}

const y = (el: Element | null) => Number(el?.getAttribute("data-y"));

describe("RankingEvolutionChart", () => {
  it("trace un point de position scratch par étape", () => {
    const { container } = renderChart();

    const points = container.querySelectorAll('[data-role="scratch"]');
    expect([...points].map((p) => p.getAttribute("data-step"))).toEqual([
      "swim",
      "t1",
      "bike",
      "t2",
      "run",
    ]);
  });

  it("trace une barre de position sur le segment isolé par étape", () => {
    const { container } = renderChart();

    expect(container.querySelectorAll('[data-role="segment"]').length).toBe(5);
  });

  it("place la meilleure position en haut du graphique", () => {
    const { container } = renderChart();

    const meilleure = container.querySelector('[data-role="scratch"][data-step="run"]'); // 56e
    const pire = container.querySelector('[data-role="scratch"][data-step="swim"]'); // 91e
    expect(y(meilleure)).toBeLessThan(y(pire));
  });

  it("calcule ses bornes sur les positions de la course, pas sur une échelle figée", () => {
    const { container } = render(
      <RankingEvolutionChart
        steps={[
          { segment: "swim", scratch_position: 3, segment_position: 4 },
          { segment: "run", scratch_position: 1, segment_position: 2 },
        ]}
        eventType="aquathlon"
      />,
    );

    // Sur une course où l'athlète oscille entre la 1re et la 4e place, l'écart
    // vertical entre ses deux points doit rester lisible, pas écrasé.
    const premier = container.querySelector('[data-role="scratch"][data-step="run"]');
    const troisieme = container.querySelector('[data-role="scratch"][data-step="swim"]');
    expect(y(troisieme) - y(premier)).toBeGreaterThan(20);
  });

  it("reste un bandeau large plutôt qu'un pavé", () => {
    const { container } = renderChart();

    const [, , largeur, hauteur] = container
      .querySelector("svg")!
      .getAttribute("viewBox")!
      .split(" ")
      .map(Number);
    // Le SVG occupe toute la largeur de la carte : c'est son rapport qui fixe
    // sa hauteur rendue. Au-delà de 0,3 il occupait la moitié de l'écran.
    expect(hauteur / largeur).toBeLessThanOrEqual(0.3);
  });

  it("gradue l'axe des positions", () => {
    const { container } = renderChart();

    const graduations = [...container.querySelectorAll("[data-tick]")].map(
      (tick) => tick.textContent,
    );
    expect(graduations.length).toBeGreaterThanOrEqual(3);
    // Bornes lues sur la course : la meilleure position (56e) et la pire (112e)
    // doivent tomber dans l'intervalle gradué.
    expect(Number(graduations[0])).toBeLessThanOrEqual(56);
    expect(Number(graduations[graduations.length - 1])).toBeGreaterThanOrEqual(112);
  });

  it("dit ce que représentent la ligne et les barres", () => {
    const { container } = renderChart();

    const legende = container.querySelector("[data-legend]") as HTMLElement;
    expect(within(legende).getByText(/classement scratch/i)).toBeTruthy();
    expect(within(legende).getByText(/sur le segment/i)).toBeTruthy();
  });

  it("affiche l'étape et la position scratch au survol d'un point", async () => {
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="scratch"][data-step="bike"]')!);

    const infobulle = screen.getByRole("tooltip");
    expect(infobulle.textContent).toContain("Vélo");
    expect(infobulle.textContent).toContain("74");
  });

  it("affiche la position sur le segment au survol d'une barre", async () => {
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="segment"][data-step="bike"]')!);

    const infobulle = screen.getByRole("tooltip");
    expect(infobulle.textContent).toContain("Vélo");
    expect(infobulle.textContent).toContain("68");
  });

  it("ne montre qu'une seule infobulle à la fois", async () => {
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="scratch"][data-step="swim"]')!);
    await user.hover(container.querySelector('[data-role="scratch"][data-step="run"]')!);

    expect(screen.getAllByRole("tooltip").length).toBe(1);
    expect(screen.getByRole("tooltip").textContent).toContain("56");
  });

  it("n'affiche aucune infobulle tant que rien n'est survolé", () => {
    renderChart();

    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("ne met plus aucun texte dans le SVG", () => {
    const { container } = renderChart();
    expect(container.querySelectorAll("svg text").length).toBe(0);
  });

  it("écrit la position de chaque étape sans survol", () => {
    // WCAG 1.4.13 : l'infobulle au survol était le seul accès au chiffre, donc
    // au doigt la courbe ne disait de quelle place à quelle place on allait.
    // `getAllByText` et non `getByText` : STEPS porte deux fois la position 91.
    renderChart();
    for (const etape of STEPS) {
      expect(screen.getAllByText(String(etape.scratch_position)).length).toBeGreaterThan(0);
    }
  });

  it("garde une hauteur en pixels, pour que les libellés HTML s'alignent", () => {
    const { container } = renderChart();
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("preserveAspectRatio")).toBe("none");
    expect((svg as unknown as HTMLElement).style.height).toBe("210px");
  });

  // jsdom normalise `calc()` : `calc(40px + 25% - 6px)` devient
  // `calc(25% + 34px)`, donc chercher la sous-chaîne "40px" ne prouve rien —
  // elle disparaît par simplification arithmétique sans que le défaut soit
  // corrigé. On extrait le terme constant en px et on vérifie sa valeur : un
  // marqueur juste porte toujours son propre décalage de centrage (-6px), quel
  // que soit le terme en %; s'il portait encore la gouttière en plus, jsdom
  // l'aurait fondue dans ce même terme (34px au lieu de -6px).
  const pxTerm = (calc: string) => {
    // jsdom sérialise `calc()` avec le signe porté par l'opérateur
    // ("25% - 6px"), jamais collé au nombre ("-6px") : le capturer séparément
    // est nécessaire pour ne pas lire "6" là où c'est "-6".
    const [, sign, digits] = calc.match(/([+-])\s*(\d+(?:\.\d+)?)px/)!;
    return (sign === "-" ? -1 : 1) * Number(digits);
  };

  it("mesure les abscisses des marqueurs sur la largeur du SVG, pas sur celle du conteneur", () => {
    // Un `%` de `left` se résout contre la padding-box du bloc conteneur. Posé
    // directement sur le conteneur, qui réserve 40px de gouttière à gauche, un
    // marqueur dériverait de 40px × sa position — la gouttière entière sur la
    // dernière étape (#480, RESP-2 ; même défaut que Histogram, task 5).
    const { container } = renderChart();

    const marker = container.querySelector('[data-role="scratch"]') as HTMLElement;
    expect(pxTerm(marker.style.left)).toBe(-6);
    expect(marker.style.pointerEvents).toBe("auto");

    const row = marker.parentElement as HTMLElement;
    expect(row.style.left).toBe("40px");
    expect(row.style.right).toBe("0px");
    expect(row.style.pointerEvents).toBe("none");
  });

  it("mesure les abscisses des libellés d'étape sur la largeur du SVG, pas sur celle du conteneur", () => {
    const { container } = renderChart();

    const label = container.querySelector("[data-step-label]") as HTMLElement;
    expect(pxTerm(label.style.left)).toBe(-40);

    const row = label.parentElement as HTMLElement;
    expect(row.style.left).toBe("40px");
    expect(row.style.right).toBe("0px");
  });
});
