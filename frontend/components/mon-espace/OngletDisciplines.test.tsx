import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation } from "@/lib/types";

const { getClubSplitMedians } = vi.hoisted(() => ({ getClubSplitMedians: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getClubSplitMedians } };
});

import { OngletDisciplines } from "./OngletDisciplines";

let numero = 0;
function resultat(extra: Partial<Participation> & { type?: string; relay?: boolean } = {}): Participation {
  numero += 1;
  const { type = "triathlon-m", relay = false, ...rest } = extra;
  return {
    id: numero,
    course: { id: numero, name: `Epreuve ${numero}`, event_date: "2026-06-01", event_type: type, provider: "k", source_url: "", is_relay: relay, is_reliable: true, distance_km: 50 },
    total_time: "1:00:00", status: "finisher", is_relay: relay, is_pending_validation: false,
    splits: { swim: "0:10:00", t1: "0:01:00", bike: "0:30:00", t2: "0:01:00", run: "0:18:00" },
    split_gap_ratio: 0,
    ...rest,
  } as Participation;
}

function afficher(selection: Participation[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OngletDisciplines participations={selection} federalOnly seasons={[2025]} />
    </QueryClientProvider>,
  );
}

beforeEach(() => getClubSplitMedians.mockReset().mockResolvedValue({ event_type: "triathlon-m", sample: 8, swim: "0:12:00", bike: "0:32:00", run: "0:17:00" }));

describe("OngletDisciplines", () => {
  it("splits my races by discipline and format with a text summary, relays excluded", async () => {
    afficher([resultat(), resultat(), resultat({ type: "duathlon-s" }), resultat({ relay: true })]);

    expect(await screen.findByRole("img", { name: /Triathlon M 2, Duathlon S 1/ })).toBeInTheDocument();
  });

  it("compares my median split with the club median on the same format", async () => {
    afficher([resultat(), resultat({ splits: { swim: "0:14:00", t1: "0:01:00", bike: "0:30:00", t2: "0:01:00", run: "0:18:00" } })]);

    expect(await screen.findByText(/Natation, vous 12:00, club 12:00/)).toBeInTheDocument();
    expect(screen.getByText(/Vélo, vous 30:00, club 32:00, 2 min plus rapide/)).toBeInTheDocument();
    expect(screen.getByText(/Course à pied, vous 18:00, club 17:00, 1 min plus lente/)).toBeInTheDocument();
    expect(getClubSplitMedians).toHaveBeenCalledWith({ event_type: "triathlon-m", federal_only: true, seasons: [2025] });
  });

  it("hides the comparison with a small club sample or without reliable splits", async () => {
    getClubSplitMedians.mockResolvedValue({ event_type: "triathlon-m", sample: 4, swim: "0:12:00", bike: "0:32:00", run: "0:17:00" });
    afficher([resultat(), resultat({ type: "duathlon-s", split_gap_ratio: null })]);

    await screen.findByRole("img", { name: /Répartition/ });
    expect(await screen.findByText("Aucune comparaison possible sur cette sélection")).toBeInTheDocument();
    expect(getClubSplitMedians).toHaveBeenCalledTimes(1);
  });

  it("shows an empty state without races", () => {
    afficher([]);

    expect(screen.getByText("Aucune épreuve sur cette sélection")).toBeInTheDocument();
  });
});
