import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ClubComposition } from "./ClubComposition";
import type { ClubComposition as ClubCompositionData } from "@/lib/types";

const COMPOSITION: ClubCompositionData = {
  gender: { M: 8, F: 4 },
  category: { S3: 5, S4: 3, V1: 2 },
};

/**
 * #653 : les deux sections de la composition club rendaient une seule teinte
 * (BarList sans `colorer`) et s'affichaient toujours dépliées.
 */
describe("ClubComposition", () => {
  it("replie les deux sections par défaut", () => {
    render(<ClubComposition composition={COMPOSITION} />);

    expect(screen.getByRole("button", { name: "Par genre" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.getByRole("button", { name: "Par catégorie" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    // Le contenu (BarList) n'est pas rendu tant que la section n'est pas dépliée.
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("déplie une section au clic et en affiche le contenu", async () => {
    render(<ClubComposition composition={COMPOSITION} />);

    await userEvent.click(screen.getByRole("button", { name: "Par genre" }));

    expect(screen.getByRole("button", { name: "Par genre" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(await screen.findByRole("img")).toBeInTheDocument();
  });

  it("colore chaque genre d'une couleur distincte", async () => {
    render(<ClubComposition composition={COMPOSITION} />);
    await userEvent.click(screen.getByRole("button", { name: "Par genre" }));

    const bars = [...document.querySelectorAll("[data-bar]")] as HTMLElement[];
    expect(bars).toHaveLength(2);
    const colors = bars.map((bar) => bar.style.background);
    expect(new Set(colors).size).toBe(2);
    expect(colors).not.toContain("var(--accent-ink)");
  });

  it("colore chaque catégorie d'une couleur distincte", async () => {
    render(<ClubComposition composition={COMPOSITION} />);
    await userEvent.click(screen.getByRole("button", { name: "Par catégorie" }));

    const bars = [...document.querySelectorAll("[data-bar]")] as HTMLElement[];
    expect(bars).toHaveLength(3);
    const colors = bars.map((bar) => bar.style.background);
    expect(new Set(colors).size).toBe(3);
    expect(colors).not.toContain("var(--accent-ink)");
  });
});
