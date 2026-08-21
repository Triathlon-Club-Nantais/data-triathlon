import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import type { Participation } from "@/lib/types";

import { ValidationQueue } from "./ValidationQueue";

function p(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id,
      name: `Course ${over.id}`,
      event_date: "2026-05-10",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time ?? "01:00:00",
    status: "finisher",
    is_relay: false,
    team_name: over.team_name ?? null,
    evidence_url: over.evidence_url ?? null,
    is_pending_validation: true,
    splits: null,
    created_at: "2026-05-11T10:00:00Z",
  };
}

describe("ValidationQueue — files vides (ETAT-3)", () => {
  it("dit qu'il n'y a rien en attente de validation", () => {
    render(<ValidationQueue participations={[]} selectedId={null} onSelect={vi.fn()} />);

    expect(screen.getByText("Aucun résultat en attente de validation")).toBeInTheDocument();
  });

  it("dit qu'il n'y a rien de signalé non conforme, sur l'onglet correspondant", async () => {
    const user = userEvent.setup();
    render(<ValidationQueue participations={[]} rejected={[]} selectedId={null} onSelect={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /Non conformes/ }));

    expect(screen.getByText("Aucun résultat signalé non conforme")).toBeInTheDocument();
  });
});

describe("ValidationQueue", () => {
  it("liste les résultats en attente avec l'athlète et l'épreuve", () => {
    const resultats = [
      p({ id: 1, athlete: { id: 1, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" } }),
      p({ id: 2, athlete: { id: 2, nom: "MARTIN", prenom: "Paul", gender: "M", club: "TCN" } }),
    ];
    render(<ValidationQueue participations={resultats} selectedId={null} onSelect={vi.fn()} />);

    expect(screen.getByText(/DUPONT/)).toBeInTheDocument();
    expect(screen.getByText(/MARTIN/)).toBeInTheDocument();
    expect(screen.getAllByText(/Course/)).toHaveLength(2);
  });

  it("distingue un résultat collectif par son nom d'équipe", () => {
    render(
      <ValidationQueue
        participations={[p({ id: 1, team_name: "Les Ecureuils" })]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("Les Ecureuils")).toBeInTheDocument();
  });

  it("affiche un état vide quand la file est vide", () => {
    render(<ValidationQueue participations={[]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText(/aucun résultat en attente/i)).toBeInTheDocument();
  });

  it("appelle onSelect au clic sur une ligne", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <ValidationQueue
        participations={[p({ id: 42 })]}
        selectedId={null}
        onSelect={onSelect}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Course 42/ }));
    expect(onSelect).toHaveBeenCalledWith(42);
  });

  it("marque la ligne sélectionnée", () => {
    render(
      <ValidationQueue
        participations={[p({ id: 1 }), p({ id: 2 })]}
        selectedId={2}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /Course 2/ })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("button", { name: /Course 1/ })).not.toHaveAttribute("aria-current");
  });

  it("affiche un onglet Non conformes et bascule la liste affichée", async () => {
    const user = userEvent.setup();
    const dupont = p({ id: 1, athlete: { id: 1, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" } });
    const martin = p({ id: 9, athlete: { id: 9, nom: "MARTIN", prenom: "Paul", gender: "M", club: "TCN" } });
    render(
      <ValidationQueue
        participations={[dupont]}
        rejected={[martin]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText(/DUPONT/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /non conformes/i }));
    expect(screen.getByText(/MARTIN/)).toBeInTheDocument();
    expect(screen.queryByText(/DUPONT/)).not.toBeInTheDocument();
  });

  it("porte les onglets à la taille tactile minimale (24 px, #479)", () => {
    // WCAG 2.2 2.5.8 : 24 px CSS minimum. Sans padding, les onglets ne
    // faisaient que la hauteur de leur texte, ~20 px.
    render(
      <ValidationQueue participations={[p({ id: 1 })]} selectedId={null} onSelect={vi.fn()} />,
    );

    const file = screen.getByRole("button", { name: /^File/ });
    const nonConformes = screen.getByRole("button", { name: /non conformes/i });
    expect(Number.parseInt(file.style.minHeight, 10)).toBeGreaterThanOrEqual(24);
    expect(Number.parseInt(nonConformes.style.minHeight, 10)).toBeGreaterThanOrEqual(24);
  });
});
