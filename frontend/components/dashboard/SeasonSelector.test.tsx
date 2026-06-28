import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeasonSelector, buildSeasonsHref } from "./SeasonSelector";
import { currentSeason, seasonLabel } from "@/lib/utils/season";
import type { Season } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const CS = currentSeason();
const SEASONS: Season[] = [
  { start_year: CS, label: seasonLabel(CS), event_count: 0, participation_count: 0, is_current: true },
  { start_year: 2023, label: "Saison 2023 — 2024", event_count: 3, participation_count: 12, is_current: false },
];

describe("buildSeasonsHref", () => {
  it("omet le paramètre quand seule la saison en cours est sélectionnée", () => {
    // saison en cours par défaut → pas de ?seasons
    const href = buildSeasonsHref([currentSeason()], undefined);
    expect(href === "/dashboard" || href === "/dashboard?").toBe(true);
    expect(href).not.toContain("seasons=");
  });
  it("sérialise plusieurs saisons et préserve le scope", () => {
    const href = buildSeasonsHref([2025, 2023], "club");
    expect(href).toContain("seasons=2025%2C2023");
    expect(href).toContain("scope=club");
  });
});

describe("SeasonSelector", () => {
  it("affiche par défaut le libellé de la saison en cours", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    expect(screen.getByText(new RegExp(`Saison ${currentSeason()}`))).toBeInTheDocument();
  });
});
