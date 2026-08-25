import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AthleteBrief, Participation } from "@/lib/types";

const {
  getBenevoleQueue,
  getBenevoleRejected,
  benevoleLogin,
  validateParticipationBenevole,
  rejectParticipationBenevole,
  unrejectParticipationBenevole,
  searchAthletesBenevole,
  updateParticipationFieldsBenevole,
} = vi.hoisted(() => ({
  getBenevoleQueue: vi.fn(),
  getBenevoleRejected: vi.fn(),
  benevoleLogin: vi.fn(),
  validateParticipationBenevole: vi.fn(),
  rejectParticipationBenevole: vi.fn(),
  unrejectParticipationBenevole: vi.fn(),
  searchAthletesBenevole: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getBenevoleQueue,
      getBenevoleRejected,
      benevoleLogin,
      validateParticipationBenevole,
      rejectParticipationBenevole,
      unrejectParticipationBenevole,
      searchAthletesBenevole,
      updateParticipationFieldsBenevole,
    },
  };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import BenevolesPage from "./page";

const ATHLETE: AthleteBrief = { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "M", club: "TCN" };

function participation(id: number, over: Partial<Participation> = {}): Participation {
  return {
    id,
    athlete: { ...ATHLETE, id, prenom: `Coureur${id}` },
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
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: null,
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    is_pending_validation: true,
    ...over,
  };
}

/** Le panneau n'est en feuille que sous `md` : par défaut on simule le desktop. */
function simulerLargeur(compact: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: compact,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  simulerLargeur(false);
  getBenevoleQueue.mockResolvedValue([participation(1), participation(2), participation(3)]);
  getBenevoleRejected.mockResolvedValue([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BenevolesPage", () => {
  it("affiche le formulaire de mot de passe sur 401", async () => {
    getBenevoleQueue.mockRejectedValue(new ApiError(401, "Non autorisé"));
    render(<BenevolesPage />);

    expect(await screen.findByLabelText(/mot de passe/i)).toBeInTheDocument();
  });

  it("affiche la file après une connexion réussie", async () => {
    getBenevoleQueue.mockRejectedValueOnce(new ApiError(401, "Non autorisé"));
    getBenevoleQueue.mockResolvedValueOnce([participation(1)]);
    benevoleLogin.mockResolvedValue(null);
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.type(await screen.findByLabelText(/mot de passe/i), "secret-du-club");
    await user.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(await screen.findByText("Coureur1 HERRMANN")).toBeInTheDocument();
  });

  it("affiche directement la file quand la session est déjà valide", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1), participation(2)]);
    render(<BenevolesPage />);

    expect(await screen.findByText("Coureur1 HERRMANN")).toBeInTheDocument();
    expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument();
  });

  it("sélectionne un résultat et affiche son panneau de détail", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1)]);
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /Coureur1/ }));

    expect(screen.getByRole("button", { name: /valider ce résultat/i })).toBeInTheDocument();
  });

  it("montre l'état de réussite quand la file est épuisée", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1)]);
    validateParticipationBenevole.mockResolvedValue(participation(1, { is_pending_validation: false }));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() => expect(screen.getByText("File vide, merci !")).toBeInTheDocument());
    // La colonne de droite ne doit plus contredire l'état de réussite affiché
    // à gauche en invitant à sélectionner un résultat qui n'existe plus
    // (#490, revue de branche finale).
    expect(screen.queryByText(/Sélectionnez un résultat/)).not.toBeInTheDocument();
  });

  it("affiche un signal de chargement avant que la file ne réponde", () => {
    getBenevoleQueue.mockReturnValue(new Promise(() => {})); // ne se résout jamais dans ce test
    render(<BenevolesPage />);
    expect(screen.getByText(/chargement/i)).toBeInTheDocument();
  });

  it("propose de réessayer après un échec de chargement", async () => {
    getBenevoleQueue.mockRejectedValueOnce(new Error("Panne réseau"));
    getBenevoleQueue.mockResolvedValueOnce([participation(1)]);
    const user = userEvent.setup();
    render(<BenevolesPage />);

    const reessayer = await screen.findByRole("button", { name: /réessayer/i });
    await user.click(reessayer);

    expect(await screen.findByText("Coureur1 HERRMANN")).toBeInTheDocument();
  });

  it("enchaîne sur l'entrée suivante après une validation", async () => {
    validateParticipationBenevole.mockResolvedValue(participation(2, { is_pending_validation: false }));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    // Le panneau ne repart pas sur l'état vide : il montre déjà la suivante.
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 2, name: /Coureur3/ })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Sélectionnez un résultat/)).not.toBeInTheDocument();
  });

  it("annonce le reste de la file aux lecteurs d'écran", async () => {
    validateParticipationBenevole.mockResolvedValue(participation(1, { is_pending_validation: false }));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Résultat validé — 2 restants."),
    );
  });

  it("demande confirmation avant de quitter une entrée aux modifications non enregistrées", async () => {
    const confirmer = vi.fn().mockReturnValue(false);
    vi.stubGlobal("confirm", confirmer);
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));

    expect(confirmer).toHaveBeenCalled();
    // Refus : on reste sur l'entrée en cours, la saisie n'est pas perdue.
    expect(screen.getByRole("heading", { level: 2, name: /Coureur1/ })).toBeInTheDocument();
  });

  it("bascule sur le résultat suivant après confirmation d'abandon du brouillon", async () => {
    // Remplace l'ancien « réinitialise le panneau de détail quand on change de
    // résultat sélectionné » (#271) : jusqu'à #490, un brouillon non enregistré
    // était abandonné en silence au changement de sélection. Le garde-fou
    // l'interdit désormais — seule la confirmation acceptée déclenche la
    // bascule, qui reste le comportement observable d'origine.
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");

    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));

    expect(window.confirm).toHaveBeenCalled();
    expect(screen.getByRole("heading", { level: 2, name: /Coureur2/ })).toBeInTheDocument();
  });

  it("ouvre le panneau en feuille sous le point de rupture md", async () => {
    simulerLargeur(true);
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  });

  it("garde le panneau dans la grille au-dessus de md", async () => {
    render(<BenevolesPage />);
    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));

    expect(screen.getByRole("heading", { level: 2, name: /Coureur1/ })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offre un bouton de fermeture tactile dans la feuille mobile", async () => {
    // Sous 520 px de viewport (tous les téléphones), la feuille n'avait ni
    // bande de fond tactile ni contrôle de fermeture visible — seule sortie :
    // Échap, qu'un clavier logiciel ne propose pas (#490, revue de branche
    // finale). `{Escape}` de jsdom fonctionnant toujours, seul un vrai clic
    // sur un contrôle de fermeture peut distinguer les deux : ce test échoue
    // sans le `SheetClose` ajouté par le correctif.
    simulerLargeur(true);
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /fermer le détail du résultat/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("annonce le statut dans la feuille elle-même sous le point de rupture md", async () => {
    // L'annonce vivait hors du portail de la feuille : sans le correctif elle
    // reste un frère du `Sheet` dans l'arbre de la page plutôt qu'un
    // descendant du `dialog`, ce que cette assertion distingue (#490, revue
    // de branche finale).
    simulerLargeur(true);
    validateParticipationBenevole.mockResolvedValue(participation(2, { is_pending_validation: false }));
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    const dialogue = await screen.findByRole("dialog");
    await waitFor(() =>
      expect(within(dialogue).getByRole("status")).toHaveTextContent("Résultat validé — 2 restants."),
    );
  });

  it("ne perd pas le brouillon quand on ferme la feuille sans confirmer (Échap)", async () => {
    // La fermeture par Échap ou par un tap hors de la feuille n'est ni
    // désactivée ni interceptée par le garde-fou — celui-ci ne vit que dans
    // `selectionner`. Sans `keepMounted`, `Popup`/`Portal` démonteraient
    // `ParticipationPanel` (et le brouillon de `useBrouillon` avec) dès cette
    // fermeture, en silence (#490, revue ronde 1).
    simulerLargeur(true);
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    // Recouvrement : rouvrir la même entrée retrouve la saisie, intacte.
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByLabelText(/Dossard/)).toHaveValue("412");
  });

  it("garde le garde-fou actif après une réouverture de la même entrée", async () => {
    // Rouvrir l'entrée déjà sélectionnée ne doit pas remettre `brouillonSale`
    // à `false` en silence : le brouillon (toujours monté) n'a pas changé, et
    // le garde-fou doit encore se déclencher sur un vrai changement d'entrée
    // qui suit (#490, revue ronde 1).
    simulerLargeur(true);
    const confirmer = vi.fn().mockReturnValue(false);
    vi.stubGlobal("confirm", confirmer);
    render(<BenevolesPage />);

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    // La réouverture elle-même ne doit pas avoir consulté le garde-fou.
    expect(confirmer).not.toHaveBeenCalled();

    // Le reste de la file est inerte tant que la feuille modale est ouverte
    // (comportement Base UI) : un vrai changement d'entrée passe forcément
    // par une fermeture d'abord, exactement comme un bénévole le ferait.
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));

    expect(confirmer).toHaveBeenCalled();
    // Refus : on reste sur Coureur1 — le rouvrir retrouve la saisie intacte.
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByLabelText(/Dossard/)).toHaveValue("412");
  });

  it("signale un résultat non conforme et le fait passer dans l'onglet non-conformes", async () => {
    const pendante = participation(1, { is_rejected: false });
    getBenevoleQueue.mockResolvedValue([pendante]);
    getBenevoleRejected.mockResolvedValue([]);
    rejectParticipationBenevole.mockResolvedValue(participation(1, { is_rejected: true }));
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /Coureur1/ }));
    await user.click(screen.getByRole("button", { name: /signaler non conforme/i }));
    await user.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() => expect(rejectParticipationBenevole).toHaveBeenCalledWith(1));
    expect(screen.queryByRole("button", { name: /Coureur1/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /non conformes/i }));
    expect(screen.getByRole("button", { name: /Coureur1/ })).toBeInTheDocument();
  });

  it("annule un rejet et fait revenir le résultat dans la file", async () => {
    const rejetee = participation(1, { is_rejected: true });
    getBenevoleQueue.mockResolvedValue([]);
    getBenevoleRejected.mockResolvedValue([rejetee]);
    unrejectParticipationBenevole.mockResolvedValue(participation(1, { is_rejected: false }));
    const user = userEvent.setup();
    render(<BenevolesPage />);

    await user.click(await screen.findByRole("button", { name: /non conformes/i }));
    await user.click(screen.getByRole("button", { name: /Coureur1/ }));
    await user.click(screen.getByRole("button", { name: /annuler le rejet/i }));

    await waitFor(() => expect(unrejectParticipationBenevole).toHaveBeenCalledWith(1));
    await user.click(screen.getByRole("button", { name: /^file/i }));
    expect(screen.getByRole("button", { name: /Coureur1/ })).toBeInTheDocument();
  });
});
