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

  it("n'écrit qu'un mois sur deux, en gardant le plus récent", () => {
    const byMonth = {
      "2025-09": 1, "2025-10": 2, "2025-11": 3, "2025-12": 4,
      "2026-01": 5, "2026-02": 6,
    };
    const { container } = render(<MonthlyTrend byMonth={byMonth} />);
    const mois = [...container.querySelectorAll("[data-month-label]")].map(
      (n) => n.textContent,
    );
    // Une colonne porte toujours son span, vide ou non : elle réserve la place qui
    // aligne les barres de la rangée. Un mois sur deux est écrit, et c'est le plus
    // récent qui l'est toujours — donc on compte les libellés **non vides**.
    expect(mois.length).toBe(6);
    expect(mois.filter((m) => m !== "").length).toBe(3);
    expect(mois.at(-1)).not.toBe("");
  });

  it("récapitule la tendance pour un lecteur d'écran", () => {
    render(<MonthlyTrend byMonth={{ "2026-01": 7, "2026-02": 20 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Activité mensuelle sur 2 mois, de 7 à 20 dossards.",
    );
  });
});
