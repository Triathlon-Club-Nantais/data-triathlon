import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { currentSeason } from "@/lib/utils/season";

const listAthleteSeasonActivity = vi.fn();
const listSeasons = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    listAthleteSeasonActivity: (opts: unknown) => listAthleteSeasonActivity(opts),
    listSeasons: (opts: unknown) => listSeasons(opts),
  },
}));

// SeasonSelector est un composant client : `usePathname`/`useSearchParams`
// doivent être mockés pour que le rendu de la page (RSC) ne plante pas. La
// query string est mutable : la ligne de tags ne se rend qu'à deux saisons.
const url = vi.hoisted(() => ({ qs: "" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/club/athletes",
  useSearchParams: () => new URLSearchParams(url.qs),
}));

import AthletesSeasonPage from "./page";

beforeEach(() => {
  url.qs = "";
  listAthleteSeasonActivity.mockReset().mockResolvedValue([
    { id: 1, nom: "DUPONT", prenom: "Jean", participation_count: 2 },
  ]);
  listSeasons.mockReset().mockResolvedValue([
    { start_year: currentSeason(), label: "Saison en cours", event_count: 1, participation_count: 2, is_current: true },
  ]);
});

async function renderPage(searchParams: Record<string, string | undefined> = {}) {
  const ui = await AthletesSeasonPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("/club/athletes", () => {
  it("appelle l'API scopée club, saison en cours par défaut", async () => {
    await renderPage();

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club", seasons: [currentSeason()] }),
    );
  });

  it("rend la liste des athlètes actifs renvoyée par l'API", async () => {
    await renderPage();

    expect(screen.getByText("DUPONT")).toBeInTheDocument();
  });

  it("lit ?seasons= dans l'URL et l'utilise à la place de la saison en cours (US2)", async () => {
    await renderPage({ seasons: "2023" });

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club", seasons: [2023] }),
    );
  });

  it("rend le sélecteur de saison, alimenté par apiServer.listSeasons", async () => {
    await renderPage();

    expect(listSeasons).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }));
    expect(screen.getByLabelText("Choisir les saisons")).toBeInTheDocument();
  });

  it("filtre aux disciplines fédérales par défaut, comme /dashboard et /club (#382)", async () => {
    await renderPage();

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: true }),
    );
  });

  it("lit ?sports=all pour inclure les autres disciplines (#382)", async () => {
    await renderPage({ sports: "all" });

    expect(listAthleteSeasonActivity).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: undefined }),
    );
  });

  it("rend le DisciplineToggle (#382)", async () => {
    await renderPage();

    expect(screen.getByText("Inclure les autres disciplines")).toBeInTheDocument();
  });

  it("rattache la ligne de tags à l'en-tête, pas à la liste (revue UI/UX)", async () => {
    // Posée en enfant du `space-y-8`, la ligne se retrouvait à 32 px de
    // l'en-tête **et** 32 px de la liste : rien ne disait à quoi elle
    // appartenait. Groupée avec l'en-tête, sa distance au titre est plus
    // courte que sa distance à la liste.
    url.qs = "seasons=2023,2024";
    await renderPage({ seasons: "2023,2024" });

    const tags = screen.getByTestId("season-tags");
    const groupe = tags.parentElement;

    expect(groupe).not.toBeNull();
    expect(groupe).toContainElement(screen.getByRole("heading", { name: "Athlètes par saison" }));
    expect(groupe).not.toContainElement(screen.getByText("DUPONT"));
  });

  it("aligne les tags comme le slot d'actions, qui bascule au palier sm (revue UI/UX)", async () => {
    url.qs = "seasons=2023,2024";
    await renderPage({ seasons: "2023,2024" });

    expect(screen.getByTestId("season-tags")).toHaveClass("justify-start", "sm:justify-end");
  });
});
