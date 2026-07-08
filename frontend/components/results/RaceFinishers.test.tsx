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
    splits: over.splits ?? null,
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

  it("duathlon : colonnes Course 1 / Vélo / Course 2 avec les temps (clés backend course1/course2)", () => {
    const dua = [
      p({
        id: 1,
        nom: "BAZLEY",
        status: "finisher",
        rank_overall: 1,
        total_time: "00:56:19",
        splits: { course1: "00:16:24", bike: "00:31:00", course2: "00:08:55" },
      } as Partial<Participation> & { id: number; nom: string }),
    ];
    render(<RaceFinishers participations={dua} tcnCount={0} eventType="duathlon-s" />);
    // En-têtes sport-aware
    expect(screen.getByText("Course 1")).toBeInTheDocument();
    expect(screen.getByText("Course 2")).toBeInTheDocument();
    expect(screen.queryByText("Natation")).not.toBeInTheDocument();
    // Temps des deux courses à pied affichés
    expect(screen.getByText("00:16:24")).toBeInTheDocument();
    expect(screen.getByText("00:08:55")).toBeInTheDocument();
  });

  it("masque les colonnes de split vides pour tous les participants (T1/T2 du duathlon Nozeen)", () => {
    const dua = [
      p({
        id: 1,
        nom: "BAZLEY",
        status: "finisher",
        rank_overall: 1,
        total_time: "00:56:19",
        splits: { course1: "00:16:24", bike: "00:31:00", course2: "00:08:55" },
      } as Partial<Participation> & { id: number; nom: string }),
      p({
        id: 2,
        nom: "VALLAEYS",
        status: "finisher",
        rank_overall: 2,
        total_time: "00:57:38",
        splits: { course1: "00:16:51", bike: "00:31:44", course2: "00:09:04" },
      } as Partial<Participation> & { id: number; nom: string }),
    ];
    render(<RaceFinishers participations={dua} tcnCount={0} eventType="duathlon-s" />);
    // Aucun participant n'a de T1/T2 → colonnes masquées.
    expect(screen.queryByText("T1")).not.toBeInTheDocument();
    expect(screen.queryByText("T2")).not.toBeInTheDocument();
    // Les colonnes renseignées restent.
    expect(screen.getByText("Course 1")).toBeInTheDocument();
    expect(screen.getByText("Vélo")).toBeInTheDocument();
    expect(screen.getByText("Course 2")).toBeInTheDocument();
  });

  it("conserve une colonne renseignée pour au moins un participant", () => {
    const dua = [
      p({
        id: 1,
        nom: "AVEC_T1",
        status: "finisher",
        rank_overall: 1,
        total_time: "00:56:19",
        splits: { course1: "00:16:24", t1: "00:00:30", bike: "00:31:00", course2: "00:08:55" },
      } as Partial<Participation> & { id: number; nom: string }),
      p({
        id: 2,
        nom: "SANS_T1",
        status: "finisher",
        rank_overall: 2,
        total_time: "00:57:38",
        splits: { course1: "00:16:51", bike: "00:31:44", course2: "00:09:04" },
      } as Partial<Participation> & { id: number; nom: string }),
    ];
    render(<RaceFinishers participations={dua} tcnCount={0} eventType="duathlon-s" />);
    // T1 renseigné pour un seul → colonne conservée, "—" pour l'autre.
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.getByText("00:00:30")).toBeInTheDocument();
  });
});
