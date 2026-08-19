import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("écrit la variante orange en `--tcn-orange-deeper`, seul token à tenir 4,5:1 (revue UI/UX)", () => {
    // 12 px / 700 est du texte courant, donc 4,5:1 (WCAG 1.4.3) : sur
    // `--tcn-orange-12` composé sur le papier, `--tcn-orange` ne valait que
    // 2,88:1. La ligne de tags de saison (#445) fait de ces pastilles le seul
    // contenu de leur ligne, plus une décoration en bout de barre d'outils.
    render(<Badge variant="orange">Saison 2025 — 2026</Badge>);

    const pastille = screen.getByText("Saison 2025 — 2026");
    expect(pastille.style.color).toBe("var(--tcn-orange-deeper)");
    expect(pastille.style.background).toBe("var(--tcn-orange-12)");
  });

  it("laisse les autres variantes intactes", () => {
    render(
      <>
        <Badge>neutre</Badge>
        <Badge variant="ink">encre</Badge>
      </>,
    );

    expect(screen.getByText("neutre").style.color).toBe("var(--tcn-ink)");
    expect(screen.getByText("encre").style.background).toBe("var(--tcn-ink)");
  });
});
