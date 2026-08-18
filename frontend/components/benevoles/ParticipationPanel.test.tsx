import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Participation } from "@/lib/types";

const {
  validateParticipationBenevole,
  renameCourseBenevole,
  reassignParticipationBenevole,
  searchAthletes,
  updateParticipationFieldsBenevole,
  rejectParticipationBenevole,
} = vi.hoisted(() => ({
  validateParticipationBenevole: vi.fn(),
  renameCourseBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
  searchAthletes: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
  rejectParticipationBenevole: vi.fn(),
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
      updateParticipationFieldsBenevole,
      rejectParticipationBenevole,
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
    club: null,
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
  beforeEach(() => {
    vi.clearAllMocks();
  });

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

  // --- #437 : champs éditables ---------------------------------------------

  it("enregistre les quatre champs modifiés en un seul appel", async () => {
    const corrigee = participation({ bib_number: "42", rank_overall: 3, club: "TCN", category: "V2" });
    updateParticipationFieldsBenevole.mockResolvedValue(corrigee);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await user.type(screen.getByLabelText(/dossard/i), "42");
    await user.type(screen.getByLabelText(/place au général/i), "3");
    await user.type(screen.getByLabelText(/^club/i), "TCN");
    await user.type(screen.getByLabelText(/catégorie/i), "V2");
    await user.click(screen.getByRole("button", { name: /enregistrer les modifications/i }));

    await waitFor(() =>
      expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(7, {
        bib_number: "42",
        rank_overall: 3,
        club: "TCN",
        category: "V2",
      }),
    );
    expect(onChanged).toHaveBeenCalledWith(corrigee);
  });

  it("signale un conflit de dossard en français", async () => {
    updateParticipationFieldsBenevole.mockRejectedValue(
      new ApiError(409, "Ce dossard est déjà attribué à un autre participant de cette épreuve."),
    );
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await user.type(screen.getByLabelText(/dossard/i), "9");
    await user.click(screen.getByRole("button", { name: /enregistrer les modifications/i }));

    expect(
      await screen.findByText("Ce dossard est déjà attribué à un autre participant de cette épreuve."),
    ).toBeInTheDocument();
  });

  // --- #437 : signalement non conforme -------------------------------------

  it("signale non conforme après confirmation", async () => {
    const rejetee = participation({ is_rejected: true });
    rejectParticipationBenevole.mockResolvedValue(rejetee);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await user.click(screen.getByRole("button", { name: /signaler non conforme/i }));
    await user.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() => expect(rejectParticipationBenevole).toHaveBeenCalledWith(7));
    expect(onChanged).toHaveBeenCalledWith(rejetee);
  });

  it("n'appelle rien si le signalement n'est pas confirmé", async () => {
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /signaler non conforme/i }));

    expect(rejectParticipationBenevole).not.toHaveBeenCalled();
  });

  // --- Revue finale (#437) : les actions qui 404ent sur une entrée rejetée --

  it("masque le renommage, la réattribution, l'édition de champs et la validation sur une entrée rejetée", () => {
    render(<ParticipationPanel participation={participation({ is_rejected: true })} onChanged={vi.fn()} />);

    expect(screen.queryByLabelText(/nom de l.épreuve/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/réattribuer à/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/dossard/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/place au général/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^club/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/catégorie/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /valider ce résultat/i })).not.toBeInTheDocument();

    expect(screen.getByText(/annulez d.abord le rejet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /annuler le rejet/i })).toBeInTheDocument();
  });

  it("affiche à nouveau tous les blocs d'édition une fois le rejet annulé", () => {
    render(<ParticipationPanel participation={participation({ is_rejected: false })} onChanged={vi.fn()} />);

    expect(screen.getByLabelText(/nom de l.épreuve/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/réattribuer à/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/dossard/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /valider ce résultat/i })).toBeInTheDocument();
    expect(screen.queryByText(/annulez d.abord le rejet/i)).not.toBeInTheDocument();
  });
});
