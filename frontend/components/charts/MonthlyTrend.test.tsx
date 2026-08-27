import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MonthlyTrend } from "./MonthlyTrend";

describe("MonthlyTrend", () => {
  it("affiche un état vide quand aucune donnée mensuelle", () => {
    render(<MonthlyTrend byMonth={{}} />);
    expect(screen.getByText("Pas encore de données mensuelles.")).toBeInTheDocument();
  });

  it("garde une hauteur minimale visible même à zéro résultat", () => {
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 0, "2026-02": 20 }} />,
    );
    const bars = [...container.querySelectorAll(".rounded-t-sm")] as HTMLElement[];
    expect(bars[0].style.height).toBe("4%");
  });

  it("donne 100% de hauteur au mois du maximum", () => {
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 0, "2026-02": 20 }} />,
    );
    const bars = [...container.querySelectorAll(".rounded-t-sm")] as HTMLElement[];
    expect(bars[1].style.height).toBe("100%");
  });

  it("donne une hauteur strictement proportionnelle à une valeur intermédiaire", () => {
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 10, "2026-02": 20 }} />,
    );
    const bars = [...container.querySelectorAll(".rounded-t-sm")] as HTMLElement[];
    // max=20, value=10 → 50% avec range([0,100])+clamp externe ; une formule
    // range([4,100]) donnerait 52% — c'est cette divergence que ce test garde.
    expect(bars[0].style.height).toBe("50%");
  });

  it("ne garde que les 12 derniers mois, triés chronologiquement", () => {
    // 14 mois valides à cheval sur deux années : les clés `YYYY-MM` restent
    // triables lexicographiquement dans le bon ordre chronologique.
    const byMonth = {
      "2025-01": 1, "2025-02": 2, "2025-03": 3, "2025-04": 4,
      "2025-05": 5, "2025-06": 6, "2025-07": 7, "2025-08": 8,
      "2025-09": 9, "2025-10": 10, "2025-11": 11, "2025-12": 12,
      "2026-01": 13, "2026-02": 14,
    };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const bars = [...container.querySelectorAll(".rounded-t-sm")];
    expect(bars.length).toBe(12);
  });

  it("affiche la valeur de chaque barre en permanence, sans survol", () => {
    // WCAG 1.4.13 : `opacity-0` + `group-hover` et l'attribut `title` n'existent
    // ni l'un ni l'autre au doigt — sur téléphone, aucune barre ne portait de
    // chiffre.
    const { container } = render(<MonthlyTrend byMonth={{ "2026-01": 7, "2026-02": 20 }} />);
    expect(screen.getByText("7")).toBeVisible();
    expect(screen.getByText("20")).toBeVisible();
    expect(container.querySelector(".opacity-0")).toBeNull();
    expect(container.querySelector("[title]")).toBeNull();
  });

  it("écrit toujours le mois, et ne masque qu'un sur deux, en CSS, sous sm: (#480)", () => {
    // Régression : `.micro-label` n'a ni `min-height` ni `display`, donc un
    // span sans texte a une hauteur de 0 et décale sa barre — d'où le mois
    // toujours écrit. Le masquage reste voulu, mais seulement sous `sm:`
    // (spec § 4) et en `invisible` (pas `hidden`), pour que la place réservée
    // garde les barres alignées au bureau comme au téléphone.
    // Jeu tenu sur une seule année civile : un jeu à cheval sur deux années
    // ferait intervenir le remplacement forcé du masquage par le libellé
    // d'année (#650, cf. le test dédié plus bas), hors de ce que ce test
    // vérifie ici.
    const byMonth = {
      "2026-01": 1, "2026-02": 2, "2026-03": 3, "2026-04": 4,
      "2026-05": 5, "2026-06": 6,
    };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const labels = [...container.querySelectorAll("[data-month-label]")] as HTMLElement[];
    expect(labels.length).toBe(6);
    expect(labels.every((label) => label.textContent !== "")).toBe(true);

    const masked = labels.filter((label) => label.classList.contains("max-sm:invisible"));
    expect(masked.length).toBe(3);
    expect(labels.at(-1)!.classList.contains("max-sm:invisible")).toBe(false);
  });

  it("récapitule la tendance pour un lecteur d'écran", () => {
    render(<MonthlyTrend byMonth={{ "2026-01": 7, "2026-02": 20 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Activité mensuelle : janv 7, févr 20.",
    );
  });

  it("affiche l'année sur le premier mois et au changement d'année quand les 12 derniers mois chevauchent deux années civiles (#650)", () => {
    // Régression : `formatMonthShort` n'affichait que le mois abrégé, jamais
    // l'année — deux mois de même nom (ex: "janv") mais d'années différentes
    // devenaient indiscernables dès que la fenêtre glissante de 12 mois
    // chevauchait le nouvel an.
    const byMonth = {
      "2025-09": 1, "2025-10": 2, "2025-11": 3, "2025-12": 4,
      "2026-01": 5, "2026-02": 6,
    };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const labelEls = [...container.querySelectorAll("[data-month-label]")] as HTMLElement[];
    expect(labelEls.map((label) => label.textContent)).toEqual([
      "sept 2025", "oct", "nov", "déc", "janv 2026", "févr",
    ]);

    // Un libellé qui porte l'année reste visible même sous `sm:` : c'est sur
    // téléphone, carte compacte, que la désambiguïsation compte le plus — le
    // masquage un-mois-sur-deux (#480) ne doit jamais retomber sur lui, sans
    // quoi il réintroduirait l'ambiguïté que #650 corrige.
    expect(labelEls[0].classList.contains("max-sm:invisible")).toBe(false);
    expect(labelEls[4].classList.contains("max-sm:invisible")).toBe(false);
  });

  it("n'affiche jamais l'année quand les mois visibles tiennent dans une seule année civile", () => {
    const byMonth = { "2026-01": 7, "2026-02": 20, "2026-03": 3 };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const labels = [...container.querySelectorAll("[data-month-label]")].map(
      (label) => label.textContent,
    );
    expect(labels).toEqual(["janv", "févr", "mars"]);
  });

  it("porte l'année dans le résumé accessible quand les mois chevauchent deux années civiles (#650)", () => {
    const byMonth = {
      "2025-09": 1, "2025-10": 2, "2025-11": 3, "2025-12": 4,
      "2026-01": 5, "2026-02": 6,
    };
    render(<MonthlyTrend byMonth={byMonth} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Activité mensuelle : sept 2025 1, oct 2, nov 3, déc 4, janv 2026 5, févr 6.",
    );
  });

  it("n'écrête pas les mois récents sur téléphone : la colonne peut descendre sous sa largeur min-content (#480)", () => {
    // Régression : `flex-1` seul pose `min-width: auto`, donc une colonne ne
    // peut pas descendre sous la largeur min-content de son contenu — sur
    // iPhone SE (375px), les douze libellés imposaient leur largeur à la
    // rangée et les mois les plus récents étaient coupés par l'`overflow-hidden`
    // de la Card, sans scroll. `min-w-0` lève ce plancher ; `whitespace-nowrap`
    // sur le libellé et la valeur les fait déborder proprement plutôt que de
    // se casser en plusieurs lignes (ce qui décalerait l'alignement des barres).
    const { container } = render(
      <MonthlyTrend byMonth={{ "2026-01": 7, "2026-02": 20 }} />,
    );
    const columns = [...container.querySelectorAll(":scope > div > div")] as HTMLElement[];
    expect(columns.length).toBeGreaterThan(0);
    for (const column of columns) {
      expect(column.classList.contains("min-w-0")).toBe(true);
    }

    const value = screen.getByText("7");
    const label = container.querySelector("[data-month-label]") as HTMLElement;
    expect(value.classList.contains("whitespace-nowrap")).toBe(true);
    expect(label.classList.contains("whitespace-nowrap")).toBe(true);
  });
});
