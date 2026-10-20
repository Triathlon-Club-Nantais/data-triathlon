import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChiffresSaison } from "@/lib/mon-espace";
import { MesChiffres } from "./MesChiffres";

const COURANT: ChiffresSaison = { epreuves: 8, podiums: 2, km: 410, tempsSecondes: 3600 * 20, meilleurRatio: 12 };
const PRECEDENT: ChiffresSaison = { epreuves: 5, podiums: 3, km: 400, tempsSecondes: 3600 * 20, meilleurRatio: 15 };

describe("MesChiffres", () => {
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
});
