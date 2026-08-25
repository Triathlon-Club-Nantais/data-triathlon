import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { brouillonDepuis } from "@/lib/benevoles/brouillon";
import type { AthleteBrief, Participation } from "@/lib/types";
import { ChampsParticipation } from "./ChampsParticipation";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 10,
    athlete: ATHLETE,
    course: {
      id: 99,
      name: "Triathlon de Nantes",
      event_date: "2026-06-14",
      event_type: "triathlon",
      provider: "njuko",
      source_url: "https://example.test/r",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V2 M",
    bib_number: "412",
    rank_overall: 37,
    rank_category: null,
    rank_gender: null,
    total_time: "02:14:53",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

describe("ChampsParticipation", () => {
  it("rend les cinq champs éditables", () => {
    const p = participation();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={vi.fn()} />);

    expect(screen.getByLabelText(/Nom de l'épreuve/)).toHaveValue("Triathlon de Nantes");
    expect(screen.getByLabelText(/Dossard/)).toHaveValue("412");
    expect(screen.getByLabelText(/Place au général/)).toHaveValue(37);
    expect(screen.getByLabelText("Club")).toHaveValue("TCN");
    expect(screen.getByLabelText(/Catégorie/)).toHaveValue("V2 M");
  });

  it("n'affiche aucune valeur d'origine tant que rien n'a bougé", () => {
    const p = participation();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={vi.fn()} />);
    expect(screen.queryByText(/Valeur d'origine/)).not.toBeInTheDocument();
  });

  it("affiche la valeur d'origine du seul champ modifié", () => {
    const p = participation();
    render(
      <ChampsParticipation
        brouillon={{ ...brouillonDepuis(p), bib_number: "413" }}
        origine={p}
        onChange={vi.fn()}
      />,
    );
    const origines = screen.getAllByText(/Valeur d'origine/);
    expect(origines).toHaveLength(1);
    expect(origines[0]).toHaveTextContent("Valeur d'origine : 412");
  });

  it("dit « vide » plutôt que rien pour une origine absente", () => {
    const p = participation({ club: null });
    render(
      <ChampsParticipation
        brouillon={{ ...brouillonDepuis(p), club: "TCN" }}
        origine={p}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/Valeur d'origine : vide/)).toBeInTheDocument();
  });

  it("remonte chaque frappe au parent", async () => {
    const p = participation({ bib_number: null });
    const onChange = vi.fn();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={onChange} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "4");

    expect(onChange).toHaveBeenCalledWith({ bib_number: "4" });
  });
});
