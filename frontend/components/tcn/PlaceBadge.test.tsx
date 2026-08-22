import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PlaceBadge } from "./PlaceBadge";

describe("PlaceBadge", () => {
  it("écrit le tier podium en `--tcn-orange-deeper`, seul token à tenir 4,5:1 (revue UI/UX)", () => {
    // `--tcn-orange` sur `--tcn-orange-12` ne valait que 2,88:1 sur paper,
    // 3,15:1 sur surface — sous le seuil AA texte normal (16px non-gras ici).
    render(<PlaceBadge place={1} />);

    const pastille = screen.getByText("1");
    expect(pastille.style.color).toBe("var(--tcn-orange-deeper)");
    expect(pastille.style.background).toBe("var(--tcn-orange-12)");
  });

  it("laisse les autres tiers intacts", () => {
    render(
      <>
        <PlaceBadge place={5} />
        <PlaceBadge place={15} />
      </>,
    );

    expect(screen.getByText("5").style.color).toBe("var(--tcn-ink)");
    expect(screen.getByText("15").style.color).toBe("var(--tcn-text-faint)");
  });
});
