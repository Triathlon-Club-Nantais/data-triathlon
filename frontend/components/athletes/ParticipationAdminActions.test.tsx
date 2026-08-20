import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminAthlete, SessionUser } from "@/lib/types";
import { ParticipationAdminActions } from "./ParticipationAdminActions";

const { getSession, deleteParticipation, searchAthletesAdmin, reassignParticipation } = vi.hoisted(
  () => ({
    getSession: vi.fn(),
    deleteParticipation: vi.fn(),
    searchAthletesAdmin: vi.fn(),
    reassignParticipation: vi.fn(),
  }),
);

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getSession, deleteParticipation, searchAthletesAdmin, reassignParticipation },
  };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const RESULTAT = {
  id: 314,
  epreuve: "Triathlon de Nantes",
  date: "2025-06-15",
  coureur: "Jean-Marc Lemée",
  coureurId: 42,
};

/** La fiche complète, seule à porter la date de naissance qui départage. */
const HOMONYME: AdminAthlete = {
  id: 77,
  nom: "LEMÉE",
  prenom: "Jean-Marc",
  birth_date: "1991-11-04",
  gender: "M",
  club: "ASPTT NANTES",
  participations: 3,
};

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
  } as unknown as SessionUser;
}

function oublierLeCookieDePresence() {
  document.cookie = "tcn_logged_in=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ParticipationAdminActions resultat={RESULTAT} />
    </QueryClientProvider>,
  );
}

/** Ouvre la confirmation de suppression du résultat. */
async function demanderLaSuppression() {
  await userEvent.click(
    await screen.findByRole("button", { name: /supprimer le résultat/i }),
  );
}

/** Le bouton de la modale, distinct de l'accès qui l'a ouverte. */
function boutonDeConfirmation() {
  return screen.getByRole("button", { name: "Supprimer" });
}

/** Ouvre le sélecteur de rattachement et cherche un coureur. */
async function chercherUnCoureur(saisie = "lemée") {
  await userEvent.click(await screen.findByRole("button", { name: /rattacher le résultat/i }));
  await userEvent.type(screen.getByLabelText("Rattacher à"), saisie);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ParticipationAdminActions — la visibilité", () => {
  it("ne rend rien pour un visiteur anonyme", async () => {
    oublierLeCookieDePresence();

    const { container } = afficher();

    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(getSession).not.toHaveBeenCalled();
  });

  it("ne rend rien pour un connecté sans `participations:delete`", async () => {
    // `athletes:write` corrige la fiche et rien d'autre : la visibilité
    // s'évalue geste par geste (US5-AC3).
    getSession.mockResolvedValue(session(["athletes:write"]));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("ne rend rien quand la session est illisible (FR-008)", async () => {
    getSession.mockRejectedValue(new ApiError(500, "Boum"));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("n'offre pas le rattachement au porteur de `participations:reassign` seul (FR-004)", async () => {
    // Les deux pouvoirs sont couplés : le sélecteur lit la recherche gardée par
    // `athletes:read`, seule à rendre la date de naissance qui départage les
    // homonymes. Sans elle, le geste serait annoncé puis finirait en 403 (D6).
    getSession.mockResolvedValue(session(["participations:reassign"]));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("offre le rattachement au porteur des deux pouvoirs (US4-AC3)", async () => {
    getSession.mockResolvedValue(session(["participations:reassign", "athletes:read"]));

    afficher();

    expect(
      await screen.findByRole("button", {
        name: "Rattacher le résultat de « Triathlon de Nantes »",
      }),
    ).toBeInTheDocument();
    // Un pouvoir n'en offre pas un autre : pas de suppression ici.
    expect(screen.queryByRole("button", { name: /supprimer/i })).not.toBeInTheDocument();
  });

  it("offre la suppression au porteur de `participations:delete`", async () => {
    getSession.mockResolvedValue(session(["participations:delete"]));

    afficher();

    // L'intitulé accessible nomme l'épreuve : sur une page qui en aligne vingt,
    // « Supprimer » seul ne dirait pas lequel des vingt.
    expect(
      await screen.findByRole("button", {
        name: "Supprimer le résultat de « Triathlon de Nantes »",
      }),
    ).toBeInTheDocument();
  });
});

describe("ParticipationAdminActions — supprimer un résultat (US2)", () => {
  beforeEach(() => {
    getSession.mockResolvedValue(session(["participations:delete"]));
  });

  it("demande une confirmation qui nomme l'épreuve et dit l'irréversibilité", async () => {
    afficher();
    await demanderLaSuppression();

    const modale = screen.getByRole("dialog");
    expect(modale).toHaveTextContent("Triathlon de Nantes");
    expect(modale).toHaveTextContent("15/06/2025");
    expect(modale).toHaveTextContent("Jean-Marc Lemée");
    expect(modale).toHaveTextContent(/irréversible/i);
    // Rien n'est parti tant que la confirmation n'est pas donnée.
    expect(deleteParticipation).not.toHaveBeenCalled();
  });

  it("ne supprime rien si l'opérateur renonce (SC-006)", async () => {
    // Zéro suppression en une seule interaction : c'est le critère chiffré, et
    // il ne tient que si le renoncement est un chemin de sortie réel.
    afficher();
    await demanderLaSuppression();
    await userEvent.click(screen.getByRole("button", { name: "Annuler" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(deleteParticipation).not.toHaveBeenCalled();
  });

  it("supprime, rend compte et rafraîchit la page (FR-015)", async () => {
    deleteParticipation.mockResolvedValue(null);

    afficher();
    await demanderLaSuppression();
    await userEvent.click(boutonDeConfirmation());

    await waitFor(() => expect(deleteParticipation).toHaveBeenCalledWith(314));
    expect(toastSuccess).toHaveBeenCalled();
    // Les cinq indicateurs et le tableau sont calculés côté serveur : sans ce
    // rafraîchissement, la ligne supprimée resterait à l'écran.
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("rend compte du succès sans rien attendre du corps de réponse (US2-AC6)", async () => {
    // La route répond **204**, sans corps, pour un résultat validé comme pour
    // une saisie en attente de validation — la route ne distingue pas les deux
    // (`test_participations_api.py`). Or une ligne en attente ne compte dans
    // aucun des cinq indicateurs : le `toast.success` est alors le seul retour
    // explicite du geste, et il ne doit dépendre d'aucune donnée renvoyée.
    deleteParticipation.mockResolvedValue(undefined);

    afficher();
    await demanderLaSuppression();
    await userEvent.click(boutonDeConfirmation());

    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
  });

  it("explique en clair une ressource déjà disparue (FR-016, US2-AC5)", async () => {
    // Un autre administrateur est passé avant. Le message du serveur
    // (« Résultat introuvable ») décrit une requête, pas ce que l'opérateur voit
    // à l'écran : l'écran dit que la ligne n'existe plus et se remet à jour.
    deleteParticipation.mockRejectedValue(new ApiError(404, "Résultat introuvable"));

    afficher();
    await demanderLaSuppression();
    await userEvent.click(boutonDeConfirmation());

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Ce résultat n'existe plus. La page a été mise à jour.",
      ),
    );
    expect(refresh).toHaveBeenCalled();
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("n'affiche jamais une erreur technique brute", async () => {
    deleteParticipation.mockRejectedValue(new ApiError(500, "Request failed with status 500"));

    afficher();
    await demanderLaSuppression();
    await userEvent.click(boutonDeConfirmation());

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    const message = String(toastError.mock.calls[0][0]);
    expect(message).not.toMatch(/request failed|status 500/i);
    // La modale reste ouverte : l'échec n'est pas un geste accompli, et la
    // confirmation est encore là pour réessayer.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

describe("ParticipationAdminActions — rattacher un résultat (US4)", () => {
  beforeEach(() => {
    getSession.mockResolvedValue(session(["participations:reassign", "athletes:read"]));
    searchAthletesAdmin.mockResolvedValue([HOMONYME]);
  });

  it("affiche nom, prénom et date de naissance de chaque candidat", async () => {
    // Sur nom + prénom + club seuls, deux vrais homonymes du même club sont
    // indiscernables : le geste censé résorber un doublon fusionnerait deux
    // personnes distinctes, sans annulation.
    afficher();
    await chercherUnCoureur();

    const candidat = await screen.findByRole("button", { name: /LEMÉE/ });
    expect(candidat).toHaveTextContent("Jean-Marc");
    expect(candidat).toHaveTextContent("04/11/1991");
    expect(searchAthletesAdmin).toHaveBeenCalled();
  });

  it("rattache dès le choix du coureur, sans seconde validation", async () => {
    // Le choix de la destination **est** la confirmation : on ne valide pas un
    // geste dont on vient de désigner explicitement la cible (contracts/ui.md).
    reassignParticipation.mockResolvedValue({});

    afficher();
    await chercherUnCoureur();
    await userEvent.click(await screen.findByRole("button", { name: /LEMÉE/ }));

    await waitFor(() => expect(reassignParticipation).toHaveBeenCalledWith(314, 77));
    expect(toastSuccess).toHaveBeenCalled();
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("dit sans erreur qu'un résultat est déjà au nom du coureur choisi (US4-AC2)", async () => {
    // Une demande sans effet n'est pas un échec : le serveur la traite en 200
    // sans rien journaliser, et l'écran doit le dire du même ton.
    searchAthletesAdmin.mockResolvedValue([{ ...HOMONYME, id: RESULTAT.coureurId }]);

    afficher();
    await chercherUnCoureur();
    await userEvent.click(await screen.findByRole("button", { name: /LEMÉE/ }));

    expect(await screen.findByText(/déjà au nom de ce coureur/i)).toBeInTheDocument();
    expect(reassignParticipation).not.toHaveBeenCalled();
    expect(toastError).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("explique en clair un résultat déjà disparu (FR-016)", async () => {
    reassignParticipation.mockRejectedValue(new ApiError(404, "Résultat introuvable"));

    afficher();
    await chercherUnCoureur();
    await userEvent.click(await screen.findByRole("button", { name: /LEMÉE/ }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Ce résultat n'existe plus. La page a été mise à jour.",
      ),
    );
    expect(refresh).toHaveBeenCalled();
  });
});
