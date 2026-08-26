import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
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

/**
 * `app/benevoles/layout.tsx` monte `DangerConfirmProvider` autour de la page
 * en production ; Next n'applique pas les layouts quand un test rend le
 * composant de page seul, il faut donc reproduire ce montage ici (#490, revue
 * UI/UX, item 2) — sans lui, `useDangerConfirm()` lève dès le premier rendu.
 */
function renderPage() {
  return render(
    <DangerConfirmProvider>
      <BenevolesPage />
    </DangerConfirmProvider>,
  );
}

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

/**
 * Simule une vraie rotation d'écran : contrairement à `simulerLargeur`, le
 * `matchMedia` renvoyé ici garde le gestionnaire d'événement `change` que
 * `useEstCompact` y abonne, pour pouvoir le déclencher en cours de test
 * (#609) — `simulerLargeur` fige `matches` une fois pour toutes et ne
 * convient donc qu'à un rendu qui démarre déjà dans le bon état.
 */
function simulerRotation(compactInitial: boolean) {
  let matches = compactInitial;
  let gestionnaire: (() => void) | null = null;
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      get matches() {
        return matches;
      },
      addEventListener: (_evenement: string, cb: () => void) => {
        gestionnaire = cb;
      },
      removeEventListener: () => {
        gestionnaire = null;
      },
    }),
  );
  return {
    basculer(nouveauCompact: boolean) {
      matches = nouveauCompact;
      gestionnaire?.();
    },
  };
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
    renderPage();

    expect(await screen.findByLabelText(/mot de passe/i)).toBeInTheDocument();
  });

  it("affiche la file après une connexion réussie", async () => {
    getBenevoleQueue.mockRejectedValueOnce(new ApiError(401, "Non autorisé"));
    getBenevoleQueue.mockResolvedValueOnce([participation(1)]);
    benevoleLogin.mockResolvedValue(null);
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText(/mot de passe/i), "secret-du-club");
    await user.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(await screen.findByText("Coureur1 HERRMANN")).toBeInTheDocument();
  });

  it("affiche directement la file quand la session est déjà valide", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1), participation(2)]);
    renderPage();

    expect(await screen.findByText("Coureur1 HERRMANN")).toBeInTheDocument();
    expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument();
  });

  it("sélectionne un résultat et affiche son panneau de détail", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1)]);
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Coureur1/ }));

    expect(screen.getByRole("button", { name: /valider ce résultat/i })).toBeInTheDocument();
  });

  it("montre l'état de réussite quand la file est épuisée", async () => {
    getBenevoleQueue.mockResolvedValue([participation(1)]);
    validateParticipationBenevole.mockResolvedValue(participation(1, { is_pending_validation: false }));
    renderPage();

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
    renderPage();
    expect(screen.getByText(/chargement/i)).toBeInTheDocument();
  });

  it("annonce et identifie l'écran de chargement (#490, revue UI/UX, P2)", () => {
    // Un « Chargement… » nu n'était ni annoncé (pas de `role="status"`) ni
    // identifié (pas de `<h1>`) : l'écran perdait jusqu'à son titre pendant
    // l'attente.
    getBenevoleQueue.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(/chargement/i);
    expect(screen.getByRole("heading", { level: 1, name: /vérification des résultats/i })).toBeInTheDocument();
  });

  it("propose de réessayer après un échec de chargement", async () => {
    getBenevoleQueue.mockRejectedValueOnce(new Error("Panne réseau"));
    getBenevoleQueue.mockResolvedValueOnce([participation(1)]);
    const user = userEvent.setup();
    renderPage();

    const reessayer = await screen.findByRole("button", { name: /réessayer/i });
    await user.click(reessayer);

    expect(await screen.findByText("Coureur1 HERRMANN")).toBeInTheDocument();
  });

  it("ne contredit pas son invitation à réessayer (#490, revue UI/UX, P2)", async () => {
    // « Réessayez plus tard » directement au-dessus d'un bouton « Réessayer »
    // invitait à réessayer maintenant tout en le déconseillant.
    getBenevoleQueue.mockRejectedValue(new Error("Panne réseau"));
    renderPage();

    expect(await screen.findByRole("button", { name: /réessayer/i })).toBeInTheDocument();
    expect(screen.getByText("La file n'a pas pu être chargée.")).toBeInTheDocument();
    expect(screen.queryByText(/réessayez plus tard/i)).not.toBeInTheDocument();
  });

  it("enchaîne sur l'entrée suivante après une validation", async () => {
    validateParticipationBenevole.mockResolvedValue(participation(2, { is_pending_validation: false }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    // Le panneau ne repart pas sur l'état vide : il montre déjà la suivante.
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 2, name: /Coureur3/ })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Sélectionnez un résultat/)).not.toBeInTheDocument();
  });

  it("déplace le focus sur le titre du panneau après un enchaînement (WCAG 2.4.3, #490, revue UI/UX, item 1)", async () => {
    // Le panneau est démonté et remonté à chaque changement d'entrée
    // (`key={file.selectionnee.id}`) : sans le correctif, le bouton qui
    // portait le focus disparaît avec lui et le focus retombe sur `<body>`,
    // obligeant à retabuler depuis le sommet du document sur le geste le plus
    // fréquent de l'écran.
    validateParticipationBenevole.mockResolvedValue(participation(2, { is_pending_validation: false }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    const titre = await screen.findByRole("heading", { level: 2, name: /Coureur3/ });
    await waitFor(() => expect(titre).toHaveFocus());
  });

  it("réinitialise le défilement de la feuille après un enchaînement (#490, revue UI/UX, item 1)", async () => {
    // Sous `md`, `SheetContent` (`overflow-y-auto`) est le conteneur de
    // défilement et son `scrollTop` survit à l'échange d'enfant : la
    // validation se fait depuis la barre collante, donc en bas — sans le
    // correctif, la nouvelle entrée s'ouvrait sur ses champs plutôt que sur
    // le nom de l'athlète.
    simulerLargeur(true);
    validateParticipationBenevole.mockResolvedValue(participation(2, { is_pending_validation: false }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur2 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    const feuille = document.querySelector('[data-slot="sheet-content"]') as HTMLElement;
    feuille.scrollTop = 500;

    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 2, name: /Coureur3/ })).toBeInTheDocument(),
    );
    expect(feuille.scrollTop).toBe(0);
  });

  it("annonce le reste de la file aux lecteurs d'écran", async () => {
    validateParticipationBenevole.mockResolvedValue(participation(1, { is_pending_validation: false }));
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.click(screen.getByRole("button", { name: /Valider ce résultat/ }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Résultat validé — 2 restants."),
    );
  });

  it("demande confirmation avant de quitter une entrée aux modifications non enregistrées", async () => {
    // Le garde-fou passe par `DangerConfirm` (#490, revue UI/UX, item 2), plus
    // par `window.confirm` : ce dernier n'est ni traduisible, ni stylable, ni
    // testable au même titre — et sur téléphone il s'ouvrait par-dessus la
    // feuille modale sans que le produit ne le contrôle.
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));

    const confirmation = await screen.findByRole("dialog", { name: /abandonner/i });
    await userEvent.click(within(confirmation).getByRole("button", { name: /renoncer/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // Refus : on reste sur l'entrée en cours, la saisie n'est pas perdue.
    expect(screen.getByRole("heading", { level: 2, name: /Coureur1/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Dossard/)).toHaveValue("412");
  });

  it("bascule sur le résultat suivant après confirmation d'abandon du brouillon", async () => {
    // Remplace l'ancien « réinitialise le panneau de détail quand on change de
    // résultat sélectionné » (#271) : jusqu'à #490, un brouillon non enregistré
    // était abandonné en silence au changement de sélection. Le garde-fou
    // l'interdit désormais — seule la confirmation acceptée déclenche la
    // bascule, qui reste le comportement observable d'origine.
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");

    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));

    const confirmation = await screen.findByRole("dialog", { name: /abandonner/i });
    await userEvent.click(within(confirmation).getByRole("button", { name: /^abandonner$/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("heading", { level: 2, name: /Coureur2/ })).toBeInTheDocument();
  });

  it("ouvre le panneau en feuille sous le point de rupture md", async () => {
    simulerLargeur(true);
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  });

  it("garde le panneau dans la grille au-dessus de md", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));

    expect(screen.getByRole("heading", { level: 2, name: /Coureur1/ })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("conserve le brouillon en cours quand une rotation d'écran franchit le point de rupture md (#609)", async () => {
    // Avant #609, `compact ? <Sheet>…</Sheet> : panneau` plaçait le panneau
    // dans deux sous-arbres React structurellement différents : franchir `md`
    // démontait `ParticipationPanel` (et le brouillon de `useBrouillon` avec)
    // en silence — sans confirmation, sans trace. Ce test démarre en bureau,
    // saisit un brouillon, puis simule le passage en mode compact (rotation
    // d'écran) sans jamais changer d'entrée sélectionnée.
    const rotation = simulerRotation(false);
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    rotation.basculer(true);

    // La rotation seule n'ouvre pas la feuille (`feuilleOuverte` n'est posé
    // à `true` que par `selectionner`) : c'est en rouvrant la même entrée,
    // déjà sélectionnée, que le bénévole retrouve son panneau — et son
    // brouillon, s'il a survécu.
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByRole("heading", { level: 2, name: /Coureur1/ })).toBeInTheDocument();
    // Sans confirmation d'abandon : un remount aurait aussi remis `sale` à
    // `false`, masquant le défaut derrière une saisie qui semble intacte au
    // premier coup d'œil mais n'a en fait jamais été reperdue à ce stade —
    // c'est la valeur du champ, ci-dessous, qui tranche vraiment.
    expect(screen.queryByRole("dialog", { name: /abandonner/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Dossard/)).toHaveValue("412");

    // Et le trajet retour (rotation dans l'autre sens) ne perd rien non plus.
    rotation.basculer(false);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByLabelText(/Dossard/)).toHaveValue("412");
  });

  it("offre un bouton de fermeture tactile dans la feuille mobile", async () => {
    // Sous 520 px de viewport (tous les téléphones), la feuille n'avait ni
    // bande de fond tactile ni contrôle de fermeture visible — seule sortie :
    // Échap, qu'un clavier logiciel ne propose pas (#490, revue de branche
    // finale). `{Escape}` de jsdom fonctionnant toujours, seul un vrai clic
    // sur un contrôle de fermeture peut distinguer les deux : ce test échoue
    // sans le `SheetClose` ajouté par le correctif.
    simulerLargeur(true);
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /fermer le détail du résultat/i }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("porte une cible tactile de 44 px pour la fermeture de la feuille (WCAG 2.5.8, #490, revue UI/UX, item 4)", async () => {
    simulerLargeur(true);
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    const fermer = screen.getByRole("button", { name: /fermer le détail du résultat/i });
    // `p-1` (24 px) remplacé par `size-11` (44 px) : une dimension fixe
    // atteint le plancher tactile quelle que soit l'icône, `.tcn-icon-btn`
    // porte le survol et l'anneau de focus.
    expect(fermer.className).toContain("size-11");
    expect(fermer.className).toContain("tcn-icon-btn");
  });

  it("donne un nom accessible au dialogue de la feuille via `sr-only`, pas `fontSize: 0` (#490, revue UI/UX, item 9)", async () => {
    simulerLargeur(true);
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));

    const dialogue = await screen.findByRole("dialog", { name: /détail du résultat/i });
    const titre = within(dialogue).getByText("Détail du résultat");
    expect(titre.className).toContain("sr-only");
    expect(titre).not.toHaveStyle({ fontSize: "0px" });
  });

  it("annonce le statut dans la feuille elle-même sous le point de rupture md", async () => {
    // L'annonce vivait hors du portail de la feuille : sans le correctif elle
    // reste un frère du `Sheet` dans l'arbre de la page plutôt qu'un
    // descendant du `dialog`, ce que cette assertion distingue (#490, revue
    // de branche finale).
    simulerLargeur(true);
    validateParticipationBenevole.mockResolvedValue(participation(2, { is_pending_validation: false }));
    renderPage();

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
    renderPage();

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
    renderPage();

    await waitFor(() => expect(screen.getByText("Coureur1 HERRMANN")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText(/Dossard/), "412");

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur1/ }));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    // La réouverture elle-même ne doit pas avoir consulté le garde-fou : la
    // seule feuille de détail est ouverte, jamais la confirmation.
    expect(screen.queryByRole("dialog", { name: /abandonner/i })).not.toBeInTheDocument();

    // Le reste de la file est inerte tant que la feuille modale est ouverte
    // (comportement Base UI) : un vrai changement d'entrée passe forcément
    // par une fermeture d'abord, exactement comme un bénévole le ferait.
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Coureur2/ }));

    const confirmation = await screen.findByRole("dialog", { name: /abandonner/i });
    await userEvent.click(within(confirmation).getByRole("button", { name: /renoncer/i }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /abandonner/i })).not.toBeInTheDocument());

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
    renderPage();

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
    renderPage();

    await user.click(await screen.findByRole("button", { name: /non conformes/i }));
    await user.click(screen.getByRole("button", { name: /Coureur1/ }));
    await user.click(screen.getByRole("button", { name: /lever le signalement/i }));

    await waitFor(() => expect(unrejectParticipationBenevole).toHaveBeenCalledWith(1));
    await user.click(screen.getByRole("button", { name: /^file/i }));
    expect(screen.getByRole("button", { name: /Coureur1/ })).toBeInTheDocument();
  });
});
