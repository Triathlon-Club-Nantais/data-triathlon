import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Participation } from "@/lib/types";

const {
  validateParticipationBenevole,
  renameCourseBenevole,
  reassignParticipationBenevole,
  searchAthletes,
} = vi.hoisted(() => ({
  validateParticipationBenevole: vi.fn(),
  renameCourseBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
  searchAthletes: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      validateParticipationBenevole,
      renameCourseBenevole,
      reassignParticipationBenevole,
      searchAthletes,
    },
  };
});

import { ParticipationPanel } from "./ParticipationPanel";

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 7,
    athlete: { id: 1, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: 3,
      name: "Tri de Nantes",
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
    total_time: "02:15:00",
    status: "finisher",
    is_relay: false,
    team_name: null,
    evidence_url: null,
    is_pending_validation: true,
    splits: null,
    created_at: "2026-05-11T10:00:00Z",
    ...over,
  };
}

describe("ParticipationPanel", () => {
  it("affiche l'athlète, l'épreuve, le temps et le lien de la pièce justificative", () => {
    render(
      <ParticipationPanel
        participation={participation({ evidence_url: "https://exemple.fr/resultats" })}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByText("Jean DUPONT")).toBeInTheDocument();
    expect(screen.getByText("Tri de Nantes")).toBeInTheDocument();
    expect(screen.getByText("02:15:00")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /résultats/i })).toHaveAttribute(
      "href",
      "https://exemple.fr/resultats",
    );
  });

  it("n'affiche aucun lien si evidence_url est absent", () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("distingue un résultat collectif par son nom d'équipe", () => {
    render(
      <ParticipationPanel participation={participation({ team_name: "Les Ecureuils" })} onChanged={vi.fn()} />,
    );
    expect(screen.getByText("Les Ecureuils")).toBeInTheDocument();
  });

  // --- US1 : validation --------------------------------------------------

  it("valide le résultat et prévient le parent", async () => {
    const valide = participation({ is_pending_validation: false });
    validateParticipationBenevole.mockResolvedValue(valide);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await user.click(screen.getByRole("button", { name: /valider/i }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(valide));
    expect(validateParticipationBenevole).toHaveBeenCalledWith(7);
  });

  // --- US2 : renommage de l'épreuve ---------------------------------------

  it("renomme l'épreuve associée", async () => {
    const renommee = { ...participation().course, name: "Triathlon de Nantes" };
    renameCourseBenevole.mockResolvedValue(renommee);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    const champ = screen.getByLabelText(/nom de l.épreuve/i);
    await user.clear(champ);
    await user.type(champ, "Triathlon de Nantes");
    await user.click(screen.getByRole("button", { name: /enregistrer le nom/i }));

    await waitFor(() =>
      expect(renameCourseBenevole).toHaveBeenCalledWith(3, "Triathlon de Nantes"),
    );
    expect(onChanged).toHaveBeenCalled();
  });

  it("signale une collision de renommage en français", async () => {
    renameCourseBenevole.mockRejectedValue(
      new ApiError(409, "Une épreuve porte déjà ce nom à cette date (fiche #9)."),
    );
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    const champ = screen.getByLabelText(/nom de l.épreuve/i);
    await user.clear(champ);
    await user.type(champ, "Déjà prise");
    await user.click(screen.getByRole("button", { name: /enregistrer le nom/i }));

    expect(
      await screen.findByText("Une épreuve porte déjà ce nom à cette date (fiche #9)."),
    ).toBeInTheDocument();
  });

  // --- US3 : réattribution ------------------------------------------------

  it("recherche puis réattribue à un autre athlète", async () => {
    searchAthletes.mockResolvedValue([
      { id: 2, nom: "MARTIN", prenom: "Paul", gender: "M", club: "ASPTT" },
    ]);
    const reattribuee = participation({ athlete: { id: 2, nom: "MARTIN", prenom: "Paul", gender: "M", club: "ASPTT" } });
    reassignParticipationBenevole.mockResolvedValue(reattribuee);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await user.type(screen.getByLabelText(/réattribuer à/i), "Martin");
    const option = await screen.findByRole("button", { name: /Paul MARTIN/ });
    await user.click(option);

    await waitFor(() =>
      expect(reassignParticipationBenevole).toHaveBeenCalledWith(7, 2),
    );
    expect(onChanged).toHaveBeenCalledWith(reattribuee);
  });

  it("signale un conflit de réattribution en français", async () => {
    searchAthletes.mockResolvedValue([
      { id: 2, nom: "MARTIN", prenom: "Paul", gender: "M", club: "ASPTT" },
    ]);
    reassignParticipationBenevole.mockRejectedValue(
      new ApiError(409, "Ce coureur a déjà un résultat sur cette épreuve."),
    );
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await user.type(screen.getByLabelText(/réattribuer à/i), "Martin");
    const option = await screen.findByRole("button", { name: /Paul MARTIN/ });
    await user.click(option);

    expect(await screen.findByText("Ce coureur a déjà un résultat sur cette épreuve.")).toBeInTheDocument();
  });

  it("affiche un état vide quand la recherche ne trouve personne", async () => {
    searchAthletes.mockResolvedValue([]);
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await user.type(screen.getByLabelText(/réattribuer à/i), "Zzz");

    expect(await screen.findByText(/aucun coureur trouvé/i)).toBeInTheDocument();
  });

  // --- Reprise de session (revue de code) ---------------------------------

  it("prévient le parent d'une session expirée plutôt que d'afficher une erreur générique", async () => {
    validateParticipationBenevole.mockRejectedValue(new ApiError(401, "Non autorisé"));
    const onSessionExpired = vi.fn();
    const user = userEvent.setup();
    render(
      <ParticipationPanel
        participation={participation()}
        onChanged={vi.fn()}
        onSessionExpired={onSessionExpired}
      />,
    );

    await user.click(screen.getByRole("button", { name: /valider/i }));

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalled());
    expect(screen.queryByText(/réessayez plus tard/i)).not.toBeInTheDocument();
  });
});
