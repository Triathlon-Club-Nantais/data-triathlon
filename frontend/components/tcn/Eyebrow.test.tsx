import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Eyebrow } from "./Eyebrow";

describe("Eyebrow", () => {
  it("écrit le ton orange en `--tcn-orange-deeper`, seul token à tenir 4,5:1 (revue UI/UX)", () => {
    // 13 px / 700 est du texte courant, donc 4,5:1 (WCAG 1.4.3) : `--tcn-orange`
    // ne valait que 3,32 à 3,68:1 selon le fond. Composant répété 35 fois.
    render(<Eyebrow>Épreuves</Eyebrow>);

    expect(screen.getByText("Épreuves").style.color).toBe("var(--tcn-orange-deeper)");
  });

  it("laisse le ton `muted` intact", () => {
    render(<Eyebrow tone="muted">Neutre</Eyebrow>);

    expect(screen.getByText("Neutre").style.color).toBe("var(--tcn-text-faint)");
  });
});
