import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AthleteDetail, Participation, SessionUser } from "@/lib/types";

const { getSession, getAthlete } = vi.hoisted(() => ({ getSession: vi.fn(), getAthlete: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSession, getAthlete } };
});

import { SeasonRecap } from "./SeasonRecap";

const LEA = { id: 42, prenom: "Léa", nom: "Martin" };

let numero = 0;
function resultat(extra: Partial<Participation> = {}): Participation {
  numero += 1;
  return {
    id: numero,
    athlete: LEA,
    course: {
      id: 100 + numero, name: `Épreuve ${numero}`, event_date: "2026-03-01", event_type: "triathlon-m",
      provider: "klikego", source_url: "", is_relay: false, is_reliable: true,
    },
    club: "TCN", is_tcn: true, category: "SEF", bib_number: String(numero),
    rank_overall: 20, rank_category: 5, rank_gender: 8, total_time: "2:30:00", status: "finisher",
    is_relay: false, splits: null, created_at: null, is_pending_validation: false,
    ...extra,
  } as Participation;
}

function detail(participations: Participation[], challenges: AthleteDetail["challenges"] = []): AthleteDetail {
  return { athlete: LEA, participations, challenges } as AthleteDetail;
}

function afficher(season = 2025) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SeasonRecap season={season} lastClosed={2025} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
  getSession.mockResolvedValue({ id: 1, athlete: LEA, athlete_claim: null, permissions: [], roles: [], groups: [] } as unknown as SessionUser);
});

describe("SeasonRecap (#1372)", () => {
  it("counts races and podiums on validated results only, and lists the races", async () => {
    getAthlete.mockResolvedValue(detail([
      resultat({ rank_category: 2 }),
      resultat(),
      resultat({ is_pending_validation: true, rank_overall: 1 }),
    ]));
    afficher();

    expect(await screen.findByText("2 épreuves")).toBeInTheDocument();
    expect(screen.getByText("1 podium")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "01/03/2026 Épreuve 1" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "01/03/2026 Épreuve 3" })).not.toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledWith(42, { seasons: "2025" });
  });

  it("keeps the challenges of the season only", async () => {
    getAthlete.mockResolvedValue(detail([resultat()], [
      { id: 1, name: "Challenge de printemps", event_date: "2026-04-01", rank_overall: 3, ranked_count: 40, total_time: "3:00:00", courses: [] },
      { id: 2, name: "Challenge ancien", event_date: "2024-04-01", rank_overall: 1, ranked_count: 10, total_time: "3:00:00", courses: [] },
    ]));
    afficher();

    expect(await screen.findByText(/Challenge de printemps/)).toBeInTheDocument();
    expect(screen.getByText(/3e sur 40/)).toBeInTheDocument();
    expect(screen.queryByText(/Challenge ancien/)).not.toBeInTheDocument();
  });

  it("navigates back in time, never past the last closed season", async () => {
    getAthlete.mockResolvedValue(detail([resultat()]));
    afficher(2025);

    expect(await screen.findByRole("link", { name: /Saison précédente/ })).toHaveAttribute("href", "/dashboard/recap?saison=2024");
    expect(screen.queryByRole("link", { name: /Saison suivante/ })).not.toBeInTheDocument();
  });

  it("says when the season has no result", async () => {
    getAthlete.mockResolvedValue(detail([]));
    afficher();

    expect(await screen.findByText(/Aucun résultat validé sur cette saison/)).toBeInTheDocument();
  });

  it("invites a visitor without a claimed athlete to claim it", async () => {
    getSession.mockResolvedValue({ id: 1, athlete: null, athlete_claim: null, permissions: [], roles: [], groups: [] } as unknown as SessionUser);
    afficher();

    expect(await screen.findByText(/rattachez votre fiche/i)).toBeInTheDocument();
    await waitFor(() => expect(getAthlete).not.toHaveBeenCalled());
  });
});
