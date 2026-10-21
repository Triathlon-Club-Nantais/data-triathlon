import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChiffresSaison } from "@/lib/mon-espace";
import { MesChiffres } from "./MesChiffres";

const COURANT: ChiffresSaison = { epreuves: 8, podiums: 2, km: 410, sansDistance: 0, tempsSecondes: 3600 * 20, meilleurRatio: 12 };
const PRECEDENT: ChiffresSaison = { epreuves: 5, podiums: 3, km: 400, sansDistance: 0, tempsSecondes: 3600 * 20, meilleurRatio: 15 };

describe("MesChiffres", () => {
  it("wraps the tiles to the column width, not the viewport (#1781)", () => {
    render(<MesChiffres courant={COURANT} precedent={null} />);

    const grille = screen.getByText("Épreuves").closest("dl");
    expect(grille?.className).toContain("grid-cols-[repeat(auto-fit,minmax(8rem,1fr))]");
    expect(grille?.className).not.toContain("sm:");
  });

  it("shows the five figures and the recap link, without deltas when no previous season", () => {
    render(<MesChiffres courant={COURANT} precedent={null} />);

    expect(screen.getByText("Épreuves").nextSibling).toHaveTextContent("8");
    expect(screen.getByText("Podiums").nextSibling).toHaveTextContent("2");
    expect(screen.getByText("Kilomètres").nextSibling).toHaveTextContent("410");
    expect(screen.getByText("Temps en course").nextSibling).toHaveTextContent("20 h 00");
    expect(screen.getByText("Meilleur classement").nextSibling).toHaveTextContent("Top 12 %");
    expect(screen.getByRole("link", { name: "Récap de la saison passée" })).toHaveAttribute("href", "/mon-espace/recap");
    expect(screen.queryByTestId("ecart")).toBeNull();
    expect(screen.queryByText(/Écart face à la saison précédente/)).toBeNull();
  });

  it("shows signed deltas against the previous season, a lower top percent being an improvement", () => {
    render(<MesChiffres courant={COURANT} precedent={PRECEDENT} />);

    const ecarts = screen.getAllByTestId("ecart").map((node) => node.textContent);
    expect(ecarts).toEqual(["+3", "−1", "+10", "=", "mieux de 3 pts"]);
    expect(screen.getByText("Écart face à la saison précédente, à date égale")).toBeVisible();
  });

  it("words a worse ranking as a loss", () => {
    render(<MesChiffres courant={COURANT} precedent={{ ...PRECEDENT, meilleurRatio: 10 }} />);

    expect(screen.getAllByTestId("ecart")[4]).toHaveTextContent("moins bien de 2 pts");
  });

  it("shows a placeholder when there is no ranking", () => {
    render(<MesChiffres courant={{ ...COURANT, meilleurRatio: null }} precedent={null} />);

    expect(screen.getByText("Meilleur classement").nextSibling).toHaveTextContent("Pas encore de classement");
  });

  it("says at least N km and counts races without distance when some are unknown", () => {
    render(<MesChiffres courant={{ ...COURANT, sansDistance: 3 }} precedent={null} />);

    const cellule = screen.getByText("Kilomètres").nextSibling;
    expect(cellule).toHaveTextContent("au moins 410");
    expect(screen.getByText("3 épreuves sans distance")).toBeVisible();
  });

  it("uses the singular for one race without distance", () => {
    render(<MesChiffres courant={{ ...COURANT, sansDistance: 1 }} precedent={null} />);

    expect(screen.getByText("1 épreuve sans distance")).toBeVisible();
  });

  it("shows a labelled dash instead of 0 when no race has a distance", () => {
    render(<MesChiffres courant={{ ...COURANT, km: 0, sansDistance: 8 }} precedent={null} />);

    expect(screen.getByText("Distance inconnue")).toBeInTheDocument();
    expect(screen.getByText("Kilomètres").nextSibling).toHaveTextContent("—");
    expect(screen.getByText("8 épreuves sans distance")).toBeVisible();
  });

  it("shows a dash when every race is a relay (no personal distance)", () => {
    render(<MesChiffres courant={{ ...COURANT, km: 0, sansDistance: 0 }} precedent={null} />);

    expect(screen.getByText("Distance inconnue")).toBeInTheDocument();
  });

  it("keeps 0 km when there is no race", () => {
    render(<MesChiffres courant={{ ...COURANT, epreuves: 0, podiums: 0, km: 0 }} precedent={null} />);

    expect(screen.getByText("Kilomètres").nextSibling).toHaveTextContent("0");
  });

  it("hides the kilometre delta when either total is incomplete", () => {
    const { rerender } = render(<MesChiffres courant={{ ...COURANT, sansDistance: 1 }} precedent={PRECEDENT} />);
    expect(screen.getAllByTestId("ecart").map((node) => node.textContent)).toEqual(["+3", "−1", "=", "mieux de 3 pts"]);

    rerender(<MesChiffres courant={COURANT} precedent={{ ...PRECEDENT, sansDistance: 2 }} />);
    expect(screen.getAllByTestId("ecart").map((node) => node.textContent)).toEqual(["+3", "−1", "=", "mieux de 3 pts"]);
  });
});
