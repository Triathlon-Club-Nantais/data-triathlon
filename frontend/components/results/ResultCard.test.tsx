import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultCard } from "./ResultCard";
import type { Participation } from "@/lib/types";

const base: Participation = {
  id: 1,
  athlete: { id: 9, nom: "Dupont", prenom: "Marie", gender: "F", club: "TCN" },
  course: {
    id: 3,
    name: "Triathlon de Nantes",
    event_date: "2026-05-10",
    event_type: "triathlon-m",
    provider: "klikego",
    source_url: "http://x",
    is_relay: false,
  },
  club: "TCN",
  category: "S4",
  bib_number: "42",
  rank_overall: 12,
  rank_category: 2,
  rank_gender: 3,
  total_time: "02:15:30",
  status: "finisher",
  is_relay: false,
  splits: { swim: "00:25:00", t1: "00:01:10", bike: "01:05:00", t2: "00:00:50", run: "00:43:30" },
  created_at: "2026-05-11T10:00:00Z",
};

describe("ResultCard", () => {
  it("affiche le nom complet (prénom + nom) et le temps total", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("Marie Dupont")).toBeInTheDocument();
    expect(screen.getByText("02:15:30")).toBeInTheDocument();
  });

  it("affiche les segments triathlon depuis p.splits", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("Natation")).toBeInTheDocument();
    expect(screen.getByText("Vélo")).toBeInTheDocument();
    expect(screen.getByText("Course")).toBeInTheDocument();
    expect(screen.getByText("00:25:00")).toBeInTheDocument();
  });

  it("adapte les libellés pour un duathlon", () => {
    const dua: Participation = {
      ...base,
      course: { ...base.course, event_type: "duathlon-s" },
      // Clés backend : course1/course2 (cf. mapping.build_splits).
      splits: { course1: "00:18:00", bike: "00:40:00", course2: "00:20:00" },
    };
    render(<ResultCard result={dua} />);
    expect(screen.getByText("Course 1")).toBeInTheDocument();
    expect(screen.getByText("Course 2")).toBeInTheDocument();
    expect(screen.getByText("00:18:00")).toBeInTheDocument();
    expect(screen.getByText("00:20:00")).toBeInTheDocument();
  });

  it("n'affiche pas de bloc splits si splits est null", () => {
    render(<ResultCard result={{ ...base, splits: null }} />);
    expect(screen.queryByText("Natation")).not.toBeInTheDocument();
  });

  it("affiche le badge Relais quand la participation est un relais", () => {
    render(<ResultCard result={{ ...base, is_relay: true }} />);
    expect(screen.getByText("Relais")).toBeInTheDocument();
  });

  it("n'affiche pas le badge Relais pour un solo", () => {
    render(<ResultCard result={base} />);
    expect(screen.queryByText("Relais")).not.toBeInTheDocument();
  });

  it("affiche le sigle DNS à la place du temps pour un non-partant", () => {
    render(
      <ResultCard result={{ ...base, total_time: null, status: "DNS" }} />,
    );
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.queryByText("02:15:30")).not.toBeInTheDocument();
  });

  it("appelle onDelete après confirmation", async () => {
    const onDelete = vi.fn();
    render(<ResultCard result={base} onDelete={onDelete} />);
    const btn = screen.getByRole("button", { name: /supprimer/i });
    await userEvent.click(btn);
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));
    expect(onDelete).toHaveBeenCalledWith(1);
  });
});
