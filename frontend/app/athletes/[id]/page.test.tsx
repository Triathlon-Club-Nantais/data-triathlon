import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { Participation } from "@/lib/types";

const getAthlete = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: { getAthlete: (id: number) => getAthlete(id) },
}));

vi.mock("next/navigation", () => ({ notFound: vi.fn() }));

import AthletePage from "./page";

const ATHLETE = { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" };

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: ATHLETE,
    course: {
      id: over.id,
      name: over.course?.name ?? `Course ${over.id}`,
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: "01:59:00",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    course_finishers: over.course_finishers,
  };
}

async function renderAthlete(participations: Participation[]) {
  getAthlete.mockResolvedValue({ athlete: ATHLETE, participations });
  const ui = await AthletePage({ params: Promise.resolve({ id: "7" }) });
  return render(ui);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AthletePage", () => {
  it("retient le meilleur ratio, pas la meilleure place", async () => {
    await renderAthlete([
      part({ id: 1, rank_overall: 42, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 80 }),
    ]);

    expect(screen.getByText("Meilleur ratio")).toBeInTheDocument();
    expect(screen.getByText("Top 14%")).toBeInTheDocument();
    expect(screen.getByText("42e sur 300")).toBeInTheDocument();
    // La tuile « Meilleure place » garde le rang absolu minimum. On cible la
    // tuile elle-même (via son libellé) plutôt que la page entière, sans quoi
    // le test resterait vert même si la tuile disparaissait — « 20 » apparaît
    // aussi dans la pastille de la ligne correspondante du tableau.
    const label = screen.getByText("Meilleure place");
    const tile = label.parentElement?.parentElement;
    expect(tile).not.toBeNull();
    expect(within(tile as HTMLElement).getByText("20")).toBeInTheDocument();
  });

  it("affiche le nombre de classés à côté de la place, dans le tableau", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 42, course_finishers: 300 })]);

    expect(screen.getByText("/300")).toBeInTheDocument();
  });

  it("retombe sur la place seule quand le classement est incohérent", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 42, course_finishers: 20 })]);

    // Ni le « /N » de la ligne, ni un percentile : la place reste seule.
    expect(screen.queryByText("/20")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Top \d+%$/)).not.toBeInTheDocument();
    expect(screen.getByText("Meilleur ratio")).toBeInTheDocument();
  });
});
