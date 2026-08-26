import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RankingEvolutionStep } from "@/lib/types";
import { RankingEvolutionChart } from "./RankingEvolutionChart";

const STEPS: RankingEvolutionStep[] = [
  { segment: "swim", scratch_position: 91, segment_position: 88, cumulative_seconds: 1200 },
  { segment: "t1", scratch_position: 91, segment_position: 112, cumulative_seconds: 1320 },
  { segment: "bike", scratch_position: 74, segment_position: 68, cumulative_seconds: 4920 },
  { segment: "t2", scratch_position: 63, segment_position: 60, cumulative_seconds: 5040 },
  { segment: "run", scratch_position: 56, segment_position: 63, cumulative_seconds: 7440 },
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

  it("referme l'infobulle quand le pointeur quitte un marqueur de courbe", async () => {
    // Les points scratch sont du HTML posé **hors** du SVG (#480, RESP-2) :
    // un `onMouseLeave` sur le SVG ne voit jamais un pointeur qui sort d'un
    // marqueur vers l'extérieur du cadre, et l'infobulle de 210×52 restait
    // plaquée sur le graphique. Au doigt, le premier tap émet un `mouseenter`
    // synthétique et rien ne la referme jamais.
    const user = userEvent.setup();
    const { container } = renderChart();
    const marqueur = container.querySelector('[data-role="scratch"][data-step="bike"]')!;

    await user.hover(marqueur);
    expect(screen.getByRole("tooltip")).toBeTruthy();

    await user.unhover(marqueur);
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("referme l'infobulle quand le pointeur quitte une barre de segment", async () => {
    const user = userEvent.setup();
    const { container } = renderChart();
    const barre = container.querySelector('[data-role="segment"][data-step="bike"]')!;

    await user.hover(barre);
    expect(screen.getByRole("tooltip")).toBeTruthy();

    await user.unhover(barre);
    expect(screen.queryByRole("tooltip")).toBeNull();
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

    // jsdom résout entièrement un calc() qui ne mélange que des %, contrairement
    // au cas marqueur (%/px) : `calc(10% - 10%)` devient `calc(0%)`, pas une
    // sous-chaîne cherchable. On lit donc la valeur, pas le texte brut.
    const pctOf = (calc: string) => Number(calc.match(/calc\(([\d.]+)%\)/)![1]);
    const label = container.querySelector("[data-step-label]") as HTMLElement;
    // STEPS[0] sur 5 étapes : centre à 10 %, moitié d'entraxe = 10 % → 0 %.
    expect(pctOf(label.style.left)).toBeCloseTo(0, 3);

    const row = label.parentElement as HTMLElement;
    expect(row.style.left).toBe("40px");
    expect(row.style.right).toBe("0px");
  });

  it("borne la boîte du libellé d'étape à l'entraxe, jamais à une largeur fixe", () => {
    // Régression du fix bloquant #480 : des boîtes de 80px fixes se
    // chevauchaient de 31px sur cinq étapes à 375px de large (iPhone SE).
    // La largeur doit suivre 100 % / N, pas une constante.
    const pctOf = (calc: string) => Number(calc.match(/calc\(([\d.]+)%\)/)![1]);

    const { container: five } = renderChart();
    const label5 = five.querySelector("[data-step-label]") as HTMLElement;
    expect(pctOf(label5.style.width)).toBeCloseTo(100 / 5, 3);

    const { container: three } = render(
      <RankingEvolutionChart steps={STEPS.slice(0, 3)} eventType="triathlon-m" />,
    );
    const label3 = three.querySelector("[data-step-label]") as HTMLElement;
    expect(pctOf(label3.style.width)).toBeCloseTo(100 / 3, 3);

    // Largeur identique pour toutes les boîtes d'un même graphique : elles se
    // partagent l'entraxe à parts égales, pas de largeur par libellé.
    const allWidths5 = [...five.querySelectorAll("[data-step-label]")].map(
      (el) => (el as HTMLElement).style.width,
    );
    expect(new Set(allWidths5).size).toBe(1);
  });

  it("écrête le nom de l'étape à l'ellipse, mais jamais la position", () => {
    // Un libellé de source peut faire trois mots en capitales
    // (`splitColumnsFromKeys` → `sourceEntry`, cf. « COURSE A PIED ») : c'est
    // lui qui s'écrête, jamais la position — seule information que ce lot a
    // justement rendue accessible sans survol (WCAG 1.4.13).
    const { container } = render(
      <RankingEvolutionChart
        steps={[{ segment: "COURSE A PIED", scratch_position: 12, segment_position: 9 }]}
        eventType="format-inconnu"
      />,
    );

    const label = container.querySelector("[data-step-label]") as HTMLElement;
    const name = label.querySelector("span") as HTMLElement;
    const position = label.querySelector("b") as HTMLElement;

    expect(name.textContent).toBe("COURSE A PIED");
    expect(name.style.overflow).toBe("hidden");
    expect(name.style.textOverflow).toBe("ellipsis");
    expect(name.style.whiteSpace).toBe("nowrap");

    expect(position.textContent).toBe("12");
    expect(position.style.overflow).not.toBe("hidden");
    expect(position.style.textOverflow).not.toBe("ellipsis");
  });

  it("sort l'infobulle du SVG, en HTML positionné", async () => {
    // Fix B (#480) : un <text fontSize={12}> dans un viewBox étiré à 856px
    // (laptop 1280, rail déplié) tombe à 10,3px, sous le plancher de 11px, et
    // les glyphes sont compressés à 86 % horizontalement.
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="scratch"][data-step="bike"]')!);

    const infobulle = screen.getByRole("tooltip");
    expect(infobulle.tagName).toBe("DIV");
    expect(container.querySelector("svg")!.contains(infobulle)).toBe(false);
    expect(infobulle.style.pointerEvents).toBe("none");
  });

  it("garde l'infobulle dans le cadre sur une rangée plus étroite qu'elle", async () => {
    // `clamp(MIN, VAL, MAX)` vaut `max(MIN, min(VAL, MAX))` : dès que MAX
    // passe sous MIN, CSS retient MIN. Sur une rangée de moins de 210px
    // (iPhone SE : ~208px utiles une fois la gouttière retranchée),
    // `calc(100% - 210px)` devient négatif, l'infobulle se plaque à gauche
    // **et** déborde du cadre à droite de sa largeur fixe. La borne haute doit
    // donc être plancherée, et la largeur suivre la rangée quand elle rétrécit.
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="scratch"][data-step="run"]')!);

    const infobulle = screen.getByRole("tooltip");
    expect(infobulle.style.width).toBe("min(210px, 100%)");
    expect(infobulle.style.left).toContain("max(0px");
  });

  it("garde le marqueur au-dessus de l'infobulle qui le décrit", async () => {
    // Sans z-index, l'ordre du DOM fixe l'ordre de peinture entre frères : la
    // rangée de l'infobulle doit précéder celle des marqueurs, sinon
    // l'infobulle plaquée sur le bord droit par `clamp()` recouvrirait
    // entièrement le point survolé (mesuré : dernière étape à xPct=90 %,
    // infobulle ramenée à [606, 816], marqueur à x=734 ; si l'étape porte la
    // meilleure position, top=0 pour les deux, le marqueur disparaît).
    const user = userEvent.setup();
    const { container } = renderChart();

    await user.hover(container.querySelector('[data-role="scratch"][data-step="bike"]')!);

    const infobulle = screen.getByRole("tooltip");
    const rangeeInfobulle = infobulle.parentElement!;
    const marqueur = container.querySelector('[data-role="scratch"][data-step="bike"]')!;
    const rangeeMarqueurs = marqueur.parentElement!;

    // DOCUMENT_POSITION_FOLLOWING (4) : la rangée des marqueurs doit suivre
    // celle de l'infobulle dans l'arbre, donc peindre par-dessus elle.
    expect(rangeeInfobulle.compareDocumentPosition(rangeeMarqueurs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("aligne le nom de l'étape à gauche, pour que l'ellipse se lise comme une troncature", () => {
    // Centré, un span écrêté par text-overflow: ellipsis est rogné des deux
    // côtés et ne reçoit l'ellipse qu'à droite : le début disparaît sans le
    // moindre marqueur visuel — défaut déjà corrigé sur `DisciplineBar`.
    const { container } = render(
      <RankingEvolutionChart
        steps={[{ segment: "COURSE A PIED", scratch_position: 12, segment_position: 9 }]}
        eventType="format-inconnu"
      />,
    );

    const label = container.querySelector("[data-step-label]") as HTMLElement;
    const name = label.querySelector("span") as HTMLElement;
    const position = label.querySelector("b") as HTMLElement;

    expect(name.style.textAlign).toBe("left");
    // La position reste centrée (héritée de la boîte) et n'a pas sa propre
    // règle d'alignement : elle ne s'écrête jamais, gauche ou droite.
    expect(position.style.textAlign).toBe("");
  });

  it("nomme le graphique par un récapitulatif chiffré, sur le patron « X : liste. »", () => {
    // Fix D (#480) : seul récapitulatif du lot à ne rendre aucun chiffre — les
    // cinq autres graphiques suivent « X : liste. » ou « X, de A à B. ».
    const { container } = renderChart();

    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("aria-label")).toBe(
      "Évolution du classement : natation 91e, t1 91e, vélo 74e, t2 63e, course 56e.",
    );
  });

  it("affiche un état vide sans NaN quand l'épreuve ne publie aucune étape classée", () => {
    // Fix C (#480) : Math.min(...[]) === Infinity, l'échelle produit du NaN.
    // Atteignable : le backend saute toute étape sans rang.
    render(<RankingEvolutionChart steps={[]} eventType="triathlon-m" />);

    expect(screen.queryByRole("img")).toBeNull();
    expect(document.body.textContent).not.toMatch(/NaN/);
    expect(screen.getByText("Classement par étape indisponible")).toBeTruthy();
  });

  it("US5 : trace l'allure (temps cumulé) en complément du classement", () => {
    const { container } = renderChart();

    const points = container.querySelectorAll('[data-role="pace"]');
    expect([...points].map((p) => p.getAttribute("data-step"))).toEqual([
      "swim",
      "t1",
      "bike",
      "t2",
      "run",
    ]);
  });

  it("US5 : écrit le temps cumulé de chaque étape en clair, sans survol", () => {
    renderChart();

    // 1200s → 0:20:00, 7440s → 2:04:00.
    expect(screen.getByText("0:20:00")).toBeTruthy();
    expect(screen.getByText("2:04:00")).toBeTruthy();
  });

  it("US5 : n'affiche pas le bloc d'allure quand aucune étape n'a de temps cumulé", () => {
    render(
      <RankingEvolutionChart
        steps={[{ segment: "swim", scratch_position: 1, segment_position: 1 }]}
        eventType="triathlon-m"
      />,
    );

    expect(screen.queryByText(/allure/i)).toBeNull();
  });

  it("colore la légende avec un token déclaré dans la palette", () => {
    // Fix E (#480) : `--tcn-text-secondary` n'existe dans aucun `:root` de
    // `app/globals.css` — `color` retombait donc sur l'encre pleine héritée.
    const { container } = renderChart();

    const legende = container.querySelector("[data-legend]") as HTMLElement;
    expect(legende.style.color).toBe("var(--tcn-text-muted)");
  });
});
