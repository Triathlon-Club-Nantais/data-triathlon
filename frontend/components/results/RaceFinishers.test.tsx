// frontend/components/results/RaceFinishers.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { RaceFinishers } from "./RaceFinishers";

function p(over: Partial<Participation> & { id: number; nom: string }): Participation {
  return {
    id: over.id,
    athlete: { id: over.id, nom: over.nom, prenom: "T", gender: "M", club: null },
    course: { id: 1, event_name: "C", event_date: null, event_type: null },
    club: over.club ?? null,
    category: "S4",
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time ?? null,
    status: over.status ?? "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
  } as Participation;
}

describe("RaceFinishers", () => {
  const data = [
    p({ id: 1, nom: "FINISHER", status: "finisher", rank_overall: 1, total_time: "00:55:00" }),
    p({ id: 2, nom: "DNSGUY", status: "DNS" }),
    p({ id: 3, nom: "DNFGUY", status: "DNF", total_time: "01:10:00" }),
  ];

  it("affiche un badge DNS/DNF pour les non-finishers", () => {
    render(<RaceFinishers participations={data} tcnCount={0} />);
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.getByText("DNF")).toBeInTheDocument();
  });

  it("relègue les non-finishers après les finishers (DNF avant DNS)", () => {
    render(<RaceFinishers participations={data} tcnCount={0} />);
    const rows = screen.getAllByRole("button", { name: /Voir le profil/ });
    const labels = rows.map((r) => r.getAttribute("aria-label"));
    expect(labels).toEqual([
      "Voir le profil de FINISHER T",
      "Voir le profil de DNFGUY T",
      "Voir le profil de DNSGUY T",
    ]);
  });
});
