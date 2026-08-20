import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminAthlete, SessionUser } from "@/lib/types";
import { AthleteAdminPanel } from "./AthleteAdminPanel";

const { getSession, updateAthlete, getAthleteAdmin } = vi.hoisted(() => ({
  getSession: vi.fn(),
  updateAthlete: vi.fn(),
  getAthleteAdmin: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, updateAthlete, getAthleteAdmin } };
});

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const COUREUR = {
  id: 42,
  nom: "Lemée",
  prenom: "Jean-Marc",
  club: "Triathlon Club Nantais",
};

const FICHE_COMPLETE: AdminAthlete = {
  id: 42,
  nom: "Lemée",
  prenom: "Jean-Marc",
  birth_date: "1980-03-12",
  gender: "M",
  club: "Triathlon Club Nantais",
  participations: 7,
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
      <AthleteAdminPanel athlete={COUREUR} />
    </QueryClientProvider>,
  );
}

/** Ouvre la modale des corrections et rend l'accès qui vient d'être cliqué. */
async function ouvrirLesCorrections() {
  const acces = await screen.findByRole("button", { name: /corriger la fiche/i });
  await userEvent.click(acces);
  return acces;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AthleteAdminPanel — l'absence de pouvoir", () => {
  it("ne rend rien pour un visiteur anonyme", async () => {
    oublierLeCookieDePresence();

    const { container } = afficher();

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("ne rend rien pour un connecté sans aucun des quatre pouvoirs", async () => {
    getSession.mockResolvedValue(session([]));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("ne rend rien quand la session est illisible", async () => {
    // Une session illisible n'est **pas** une session sans pouvoirs, mais
    // l'écran n'affirme ni l'un ni l'autre : il n'offre rien (FR-008, US5-AC4).
    getSession.mockRejectedValue(new ApiError(500, "Boum"));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("n'offre pas les corrections d'identité au porteur de `participations:delete` seul (US5-AC3)", async () => {
    // La visibilité s'évalue geste par geste : il n'existe aucun échelon
    // « administrateur » dont un pouvoir quelconque serait la clé.
    getSession.mockResolvedValue(session(["participations:delete"]));

    const { container } = afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("n'appelle pas la session quand le cookie témoin est absent (SC-004)", async () => {
    // Le visiteur anonyme ne paie rien de plus que la page publique : pas un
    // seul appel réseau ajouté par cette feature.
    oublierLeCookieDePresence();

    const { container } = afficher();

    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(getSession).not.toHaveBeenCalled();
  });
});

describe("AthleteAdminPanel — corriger l'identité (US1)", () => {
  it("ouvre un formulaire prérempli et n'envoie que le champ corrigé", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    updateAthlete.mockResolvedValue({ ...FICHE_COMPLETE, prenom: "Jean-Michel" });

    afficher();
    await ouvrirLesCorrections();

    const nom = screen.getByLabelText("Nom");
    const prenom = screen.getByLabelText("Prénom");
    expect(nom).toHaveValue("Lemée");
    expect(prenom).toHaveValue("Jean-Marc");

    await userEvent.clear(prenom);
    await userEvent.type(prenom, "Jean-Michel");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // Le nom n'a pas bougé : il ne part pas. Ce qui n'est pas envoyé n'est pas
    // réécrit, `exclude_unset` faisant le reste côté serveur.
    await waitFor(() => expect(updateAthlete).toHaveBeenCalledWith(42, { prenom: "Jean-Michel" }));
    expect(toastSuccess).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("rafraîchit la page après une correction réussie (FR-015)", async () => {
    // Le nom en tête et les cinq indicateurs sont calculés côté serveur : sans
    // ce rafraîchissement, l'écran continue d'afficher l'ancienne identité.
    getSession.mockResolvedValue(session(["athletes:write"]));
    updateAthlete.mockResolvedValue(FICHE_COMPLETE);

    afficher();
    await ouvrirLesCorrections();
    await userEvent.type(screen.getByLabelText("Nom"), "-Durand");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(refresh).toHaveBeenCalled());
  });

  it("garde la modale ouverte et la saisie intacte sur un conflit (US1-AC3)", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    updateAthlete.mockRejectedValue(
      new ApiError(409, "Un coureur porte déjà cette identité (fiche #77)."),
    );

    afficher();
    await ouvrirLesCorrections();
    await userEvent.type(screen.getByLabelText("Nom"), "-Durand");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // Le message du serveur est déjà en français : la modale l'affiche, elle ne
    // le reformule pas (FR-010).
    expect(
      await screen.findByText("Un coureur porte déjà cette identité (fiche #77)."),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    // La saisie survit : l'opérateur corrige sa correction sans tout retaper.
    expect(screen.getByLabelText("Nom")).toHaveValue("Lemée-Durand");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("n'offre ni n'envoie la date de naissance sans `athletes:read` (US1-AC4)", async () => {
    // Un résultat ne porte pas la date de naissance : la rendre à blanc puis
    // l'enregistrer effacerait une date que l'écran n'a jamais lue. C'est
    // l'**absence de la clé** dans le corps qui garantit la non-effacement (D7).
    getSession.mockResolvedValue(session(["athletes:write"]));
    updateAthlete.mockResolvedValue(FICHE_COMPLETE);

    afficher();
    await ouvrirLesCorrections();

    expect(screen.queryByLabelText("Date de naissance")).not.toBeInTheDocument();
    expect(getAthleteAdmin).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Nom"), "-Durand");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(updateAthlete).toHaveBeenCalled());
    expect(Object.keys(updateAthlete.mock.calls[0][1])).toEqual(["nom"]);
  });

  it("préremplit la date de naissance avec `athletes:read` (US1-AC4)", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    getAthleteAdmin.mockResolvedValue(FICHE_COMPLETE);
    updateAthlete.mockResolvedValue(FICHE_COMPLETE);

    afficher();
    await ouvrirLesCorrections();

    const naissance = await screen.findByLabelText("Date de naissance");
    expect(naissance).toHaveValue("1980-03-12");
    expect(getAthleteAdmin).toHaveBeenCalledWith(42);
  });
});

describe("AthleteAdminPanel — corriger le club actuel (US3)", () => {
  it("offre le club sous `athletes:write` seul, prérempli sans lire la fiche gardée", async () => {
    // Contrairement à la date de naissance, le club voyage déjà sur la ressource
    // publique : exiger `athletes:read` pour l'éditer n'ajouterait aucune
    // protection, la valeur étant sous les yeux de tout visiteur.
    getSession.mockResolvedValue(session(["athletes:write"]));

    afficher();
    await ouvrirLesCorrections();

    expect(screen.getByLabelText("Club actuel")).toHaveValue("Triathlon Club Nantais");
    expect(getAthleteAdmin).not.toHaveBeenCalled();
  });

  it("envoie le nouveau libellé de club (US3-AC1)", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    updateAthlete.mockResolvedValue({ ...FICHE_COMPLETE, club: "ASPTT NANTES" });

    afficher();
    await ouvrirLesCorrections();
    await userEvent.clear(screen.getByLabelText("Club actuel"));
    await userEvent.type(screen.getByLabelText("Club actuel"), "ASPTT NANTES");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(updateAthlete).toHaveBeenCalledWith(42, { club: "ASPTT NANTES" }));
    expect(refresh).toHaveBeenCalled();
  });

  it("envoie `null` et non `\"\"` quand le champ est vidé (US3-AC2)", async () => {
    // « Sans club » est une valeur, la chaîne vide n'en est pas une : l'envoyer
    // créerait un club fantôme, présent dans les regroupements par libellé.
    getSession.mockResolvedValue(session(["athletes:write"]));
    updateAthlete.mockResolvedValue({ ...FICHE_COMPLETE, club: null });

    afficher();
    await ouvrirLesCorrections();
    await userEvent.clear(screen.getByLabelText("Club actuel"));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(updateAthlete).toHaveBeenCalledWith(42, { club: null }));
  });

  it("ne renvoie pas le club quand il n'a pas été touché", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    updateAthlete.mockResolvedValue(FICHE_COMPLETE);

    afficher();
    await ouvrirLesCorrections();
    await userEvent.type(screen.getByLabelText("Nom"), "-Durand");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    // Un club renvoyé à l'identique poserait le verrou sans qu'aucune correction
    // ait eu lieu, et gèlerait le libellé contre tous les imports à venir.
    await waitFor(() => expect(updateAthlete).toHaveBeenCalled());
    expect(Object.keys(updateAthlete.mock.calls[0][1])).toEqual(["nom"]);
  });
});
