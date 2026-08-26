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

  it("relie le champ modifié à sa valeur d'origine pour le lecteur d'écran (#608)", () => {
    const p = participation();
    render(
      <ChampsParticipation
        brouillon={{ ...brouillonDepuis(p), bib_number: "413" }}
        origine={p}
        onChange={vi.fn()}
      />,
    );
    const champ = screen.getByLabelText(/Dossard/);
    const note = screen.getByText(/Valeur d'origine : 412/);
    expect(note).toHaveAttribute("id");
    expect(champ).toHaveAttribute("aria-describedby", note.id);
  });

  it("ne décrit pas un champ non modifié — la note reste montée mais vide", () => {
    const p = participation();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/Dossard/)).not.toHaveAttribute("aria-describedby");
  });

  it("réserve la ligne de valeur d'origine dès le premier rendu (#490, revue UI/UX)", () => {
    // Sans la réservation, la ligne n'existe dans le DOM qu'une fois `modifie`
    // vrai : elle apparaît alors au premier caractère saisi et pousse les
    // champs suivants (et la barre d'action collante) sous le doigt du
    // bénévole. `nextElementSibling` du champ est cette ligne, montée à
    // hauteur fixe qu'elle porte ou non du texte.
    const p = participation();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={vi.fn()} />);

    // `Input` (`components/tcn/Input.tsx`) enveloppe l'`<input>` dans un `<div>`
    // de bordure : la ligne réservée est la sœur suivante de ce conteneur, pas
    // de l'`<input>` lui-même.
    const ligne = screen.getByLabelText(/Dossard/).parentElement?.nextElementSibling;
    expect(ligne).not.toBeNull();
    expect(ligne).toBeEmptyDOMElement();
    expect(ligne).toHaveStyle({ minHeight: "16px" });
  });

  it("remonte chaque frappe au parent", async () => {
    const p = participation({ bib_number: null });
    const onChange = vi.fn();
    render(<ChampsParticipation brouillon={brouillonDepuis(p)} origine={p} onChange={onChange} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "4");

    expect(onChange).toHaveBeenCalledWith({ bib_number: "4" });
  });
});
