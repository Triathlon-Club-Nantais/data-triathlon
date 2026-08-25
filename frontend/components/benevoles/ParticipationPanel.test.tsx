import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AthleteBrief, Participation } from "@/lib/types";

const {
  validateParticipationBenevole,
  renameCourseBenevole,
  reassignParticipationBenevole,
  searchAthletesBenevole,
  updateParticipationFieldsBenevole,
  rejectParticipationBenevole,
  unrejectParticipationBenevole,
} = vi.hoisted(() => ({
  validateParticipationBenevole: vi.fn(),
  renameCourseBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
  searchAthletesBenevole: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
  rejectParticipationBenevole: vi.fn(),
  unrejectParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      validateParticipationBenevole,
      renameCourseBenevole,
      reassignParticipationBenevole,
      searchAthletesBenevole,
      updateParticipationFieldsBenevole,
      rejectParticipationBenevole,
      unrejectParticipationBenevole,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import { ParticipationPanel } from "./ParticipationPanel";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };
const AUTRE: AthleteBrief = { id: 2, nom: "KERMARREC", prenom: "Hadrien", gender: "M", club: "TCN" };

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
    evidence_url: "https://example.test/resultats",
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ParticipationPanel — lecture", () => {
  it("affiche l'athlète, l'épreuve, le temps et le lien de la pièce justificative", () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    expect(screen.getByText("Mathieu HERRMANN")).toBeInTheDocument();
    expect(screen.getByText(/Triathlon de Nantes/)).toBeInTheDocument();
    expect(screen.getByText("02:14:53")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Lien vers les résultats/ })).toHaveAttribute(
      "href",
      "https://example.test/resultats",
    );
  });

  it("n'affiche aucun lien si evidence_url est absent", () => {
    render(<ParticipationPanel participation={participation({ evidence_url: null })} onChanged={vi.fn()} />);
    expect(screen.queryByRole("link", { name: /Lien vers les résultats/ })).not.toBeInTheDocument();
  });

  it("distingue un résultat collectif par son nom d'équipe", () => {
    render(
      <ParticipationPanel participation={participation({ team_name: "Les Requins" })} onChanged={vi.fn()} />,
    );
    expect(screen.getByText("Les Requins")).toBeInTheDocument();
  });
});

describe("ParticipationPanel — enregistrement unique", () => {
  it("n'offre plus qu'un seul bouton d'enregistrement", () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /Enregistrer le nom/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Enregistrer les modifications/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeInTheDocument();
  });

  it("signale les modifications non enregistrées dès la première frappe", async () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    expect(screen.queryByText(/Modifications non enregistrées/)).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");

    expect(screen.getByText(/Modifications non enregistrées/)).toBeInTheDocument();
  });

  it("enregistre le nom d'épreuve et les champs en un seul geste", async () => {
    renameCourseBenevole.mockResolvedValue({ ...participation().course, name: "Triathlon de Nantes 2026" });
    updateParticipationFieldsBenevole.mockResolvedValue(participation({ bib_number: "4123" }));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Nom de l'épreuve/), " 2026");
    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(renameCourseBenevole).toHaveBeenCalledWith(99, "Triathlon de Nantes 2026"));
    expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(10, { bib_number: "4123" });
  });

  it("valide en enregistrant d'abord le dossard saisi", async () => {
    updateParticipationFieldsBenevole.mockResolvedValue(participation({ bib_number: "4123" }));
    validateParticipationBenevole.mockResolvedValue(
      participation({ bib_number: "4123", is_pending_validation: false }),
    );
    const onChanged = vi.fn();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() => expect(validateParticipationBenevole).toHaveBeenCalledWith(10));
    expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(10, { bib_number: "4123" });
  });

  it("réattribue au moment de l'enregistrement, pas au clic sur le résultat", async () => {
    searchAthletesBenevole.mockResolvedValue([AUTRE]);
    reassignParticipationBenevole.mockResolvedValue(participation({ athlete: AUTRE }));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    expect(reassignParticipationBenevole).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(reassignParticipationBenevole).toHaveBeenCalledWith(10, 2));
  });

  it("valide un brouillon propre sans rien modifier au préalable", async () => {
    const validee = participation({ is_pending_validation: false });
    validateParticipationBenevole.mockResolvedValue(validee);
    const onChanged = vi.fn();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() => expect(validateParticipationBenevole).toHaveBeenCalledWith(10));
    expect(onChanged).toHaveBeenCalledWith(validee);
    expect(updateParticipationFieldsBenevole).not.toHaveBeenCalled();
    expect(renameCourseBenevole).not.toHaveBeenCalled();
  });

  it("affiche « Validation… », pas « Enregistrement… », en validant un brouillon propre", async () => {
    // Le geste le plus fréquent de l'écran — valider une entrée non
    // modifiée — n'enregistre rien : seul l'appel de validation tourne. Avant
    // #490 (revue de branche finale), le bouton affichait quand même
    // « Enregistrement… » pendant cet appel.
    let resoudre!: (p: Participation) => void;
    validateParticipationBenevole.mockReturnValue(
      new Promise<Participation>((resolve) => {
        resoudre = resolve;
      }),
    );
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    expect(await screen.findByRole("button", { name: "Validation…" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrement…" })).not.toBeInTheDocument();

    resoudre(participation({ is_pending_validation: false }));
    await waitFor(() => expect(validateParticipationBenevole).toHaveBeenCalled());
  });
});

describe("ParticipationPanel — erreurs", () => {
  it("nomme l'étape en échec dans une zone d'erreur unique", async () => {
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(409, "Ce dossard est déjà pris."));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Les champs n'ont pas pu être enregistrés : Ce dossard est déjà pris.",
      ),
    );
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("signale une collision de renommage en français", async () => {
    renameCourseBenevole.mockRejectedValue(new ApiError(409, "Une autre épreuve porte déjà ce nom."));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Nom de l'épreuve/), " 2026");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Une autre épreuve porte déjà ce nom."),
    );
  });

  it("signale un conflit de réattribution en français", async () => {
    searchAthletesBenevole.mockResolvedValue([AUTRE]);
    reassignParticipationBenevole.mockRejectedValue(
      new ApiError(409, "Ce coureur a déjà un résultat sur cette épreuve."),
    );
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Réattribuer/), "Kerm");
    await waitFor(() => expect(screen.getByText(/Hadrien KERMARREC/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Hadrien KERMARREC/));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Ce coureur a déjà un résultat sur cette épreuve.",
      ),
    );
  });

  it("prévient le parent d'une session expirée plutôt que d'afficher une erreur générique", async () => {
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(401, "non autorisé"));
    const onSessionExpired = vi.fn();
    render(
      <ParticipationPanel
        participation={participation()}
        onChanged={vi.fn()}
        onSessionExpired={onSessionExpired}
      />,
    );

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("ne montre jamais deux erreurs à la fois quand un rejet échoue après un enregistrement en échec", async () => {
    updateParticipationFieldsBenevole.mockRejectedValue(new ApiError(409, "Ce dossard est déjà pris."));
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Les champs n'ont pas pu être enregistrés : Ce dossard est déjà pris.",
      ),
    );

    rejectParticipationBenevole.mockRejectedValue(new ApiError(409, "Ce signalement n'a pas pu être enregistré."));
    await userEvent.click(screen.getByRole("button", { name: /Signaler non conforme/ }));
    await userEvent.click(screen.getByRole("button", { name: /Confirmer/ }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Ce signalement n'a pas pu être enregistré."),
    );
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });
});

describe("ParticipationPanel — rejet", () => {
  it("signale non conforme après confirmation et propage le résultat au parent", async () => {
    const rejetee = participation({ is_rejected: true });
    rejectParticipationBenevole.mockResolvedValue(rejetee);
    const onChanged = vi.fn();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await userEvent.click(screen.getByRole("button", { name: /Signaler non conforme/ }));
    await userEvent.click(screen.getByRole("button", { name: /Confirmer/ }));

    await waitFor(() => expect(rejectParticipationBenevole).toHaveBeenCalledWith(10));
    expect(onChanged).toHaveBeenCalledWith(rejetee);
  });

  it("n'appelle rien si le signalement n'est pas confirmé", async () => {
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /Signaler non conforme/ }));
    expect(rejectParticipationBenevole).not.toHaveBeenCalled();
  });

  it("laisse une entrée rejetée en lecture seule", () => {
    render(
      <ParticipationPanel participation={participation({ is_rejected: true })} onChanged={vi.fn()} />,
    );
    expect(screen.queryByLabelText(/Dossard/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Valider ce résultat/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Annuler le rejet/ })).toBeInTheDocument();
  });

  it("rouvre l'édition une fois le rejet annulé", () => {
    render(
      <ParticipationPanel participation={participation({ is_rejected: false })} onChanged={vi.fn()} />,
    );
    expect(screen.getByLabelText(/Dossard/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Valider ce résultat/ })).toBeInTheDocument();
  });

  it("propage la réouverture au parent une fois le rejet annulé", async () => {
    const reouverte = participation({ is_rejected: false });
    unrejectParticipationBenevole.mockResolvedValue(reouverte);
    const onChanged = vi.fn();
    render(
      <ParticipationPanel participation={participation({ is_rejected: true })} onChanged={onChanged} />,
    );

    await userEvent.click(screen.getByRole("button", { name: /Annuler le rejet/ }));

    await waitFor(() => expect(unrejectParticipationBenevole).toHaveBeenCalledWith(10));
    expect(onChanged).toHaveBeenCalledWith(reouverte);
  });
});

describe("ParticipationPanel — remontée de l'état sale", () => {
  it("prévient le parent quand le brouillon devient sale", async () => {
    const onBrouillonSale = vi.fn();
    render(
      <ParticipationPanel
        participation={participation()}
        onChanged={vi.fn()}
        onBrouillonSale={onBrouillonSale}
      />,
    );

    await userEvent.type(screen.getByLabelText(/Dossard/), "3");

    await waitFor(() => expect(onBrouillonSale).toHaveBeenLastCalledWith(true));
  });
});
