import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation } from "@/lib/types";

const { getAthlete } = vi.hoisted(() => ({ getAthlete: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getAthlete } };
});

import { OngletRecords } from "./OngletRecords";

let numero = 0;
function resultat(extra: Partial<Participation> & { date?: string; type?: string; km?: number } = {}): Participation {
  numero += 1;
  const { date = "2026-06-01", type = "triathlon-m", km = 50, ...rest } = extra;
  return {
    id: numero,
    course: { id: numero, name: `Epreuve ${numero}`, event_date: date, event_type: type, provider: "k", source_url: "", is_relay: false, is_reliable: true, distance_km: km },
    total_time: "2:00:00", status: "finisher", is_relay: false, is_pending_validation: false,
    ...rest,
  } as Participation;
}

function afficher(selection: Participation[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OngletRecords athleteId={42} federalOnly selection={selection} />
    </QueryClientProvider>,
  );
}

beforeEach(() => getAthlete.mockReset());

describe("OngletRecords", () => {
  it("shows the best of the selection, its link, and a text badge for a beaten record", async () => {
    const ancien = resultat({ date: "2025-06-01", total_time: "2:10:00" });
    const battu = resultat();
    getAthlete.mockResolvedValue({ participations: [ancien, battu] });
    afficher([battu]);

    expect(await screen.findByText("record perso")).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledWith(42, { federal_only: true });
    expect(screen.getByRole("link", { name: /Epreuve/ })).toHaveAttribute("href", `/courses/${battu.course.id}/participations/${battu.id}`);
  });

  it("labels a first time, and shows the career record when the selection best is slower", async () => {
    const premier = resultat({ type: "triathlon-s", km: 25 });
    const record = resultat({ date: "2024-06-01", total_time: "1:50:00" });
    const lent = resultat();
    getAthlete.mockResolvedValue({ participations: [record, lent, premier] });
    afficher([lent, premier]);

    expect(await screen.findByText("1re fois")).toBeInTheDocument();
    expect(screen.getByText(/Record : 1:50:00/)).toBeInTheDocument();
  });

  it("shows an empty state without a comparable time", async () => {
    getAthlete.mockResolvedValue({ participations: [] });
    afficher([]);

    expect(await screen.findByText("Aucun record sur cette sélection")).toBeInTheDocument();
  });
});
