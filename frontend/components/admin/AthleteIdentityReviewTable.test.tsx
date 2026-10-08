import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { confirmerDansLeDialog } from "@/components/admin/__tests__/dangerConfirm";
import type { IdentityReviewCandidate, IdentityReviewList, Participation, SessionUser } from "@/lib/types";

const {
  listIdentityReview, getSession, ignoreIdentityPair, confirmIdentityClub, getAthlete, detachParticipations, push,
  toastError, toastSuccess, dismissIdentityCase,
} = vi.hoisted(() => ({
  dismissIdentityCase: vi.fn(),
  listIdentityReview: vi.fn(),
  getAthlete: vi.fn(),
  detachParticipations: vi.fn(),
  push: vi.fn(),
  getSession: vi.fn(),
  ignoreIdentityPair: vi.fn(),
  confirmIdentityClub: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      listIdentityReview, getSession, ignoreIdentityPair, confirmIdentityClub, getAthlete, detachParticipations,
      dismissIdentityCase,
    },
  };
});
vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push }) }));

import { AthleteIdentityReviewTable } from "./AthleteIdentityReviewTable";

function session(permissions: string[]): SessionUser {
  return { id: 1, email: "admin@exemple.fr", permissions, roles: [], created_at: "2026-01-01T00:00:00Z" } as unknown as SessionUser;
}

const FICHE = (id: number, nom: string, prenom: string, extra = {}) => ({
  id, nom, prenom, club: null, gender: "M", categories: [], participations: 1, homonym_rank: 0, ...extra,
});

const CAS: IdentityReviewList = {
  candidates: [
    {
      reason: "same_course_bibs",
      reason_label: "Deux dossards sur une même épreuve",
      athletes: [FICHE(7, "MARTIN", "Thomas", { club: "Triathlon Club Nantais", categories: ["M25-29", "M45-49"] })],
      conflicts: [
        {
          course_id: 407, course_name: "IRONMAN Tours", event_date: "2025-06-01",
          entries: [
            { participation_id: 1, athlete_id: 7, bib: "2348", category: "M25-29", total_time: "11:19:24" },
            { participation_id: 2, athlete_id: 7, bib: "1715", category: "M45-49", total_time: "11:45:59" },
          ],
        },
      ],
      clubs: [],
    },
    {
      reason: "swapped",
      reason_label: "Nom et prénom inversés",
      athletes: [FICHE(10, "DUPONT", "Jean"), FICHE(11, "JEAN", "Dupont", { homonym_rank: 0 })],
      conflicts: [],
      clubs: [],
    },
  ],
};

const MULTI: IdentityReviewList = {
  candidates: [
    {
      reason: "multi_club",
      reason_label: "Plusieurs clubs sur une même fiche",
      athletes: [FICHE(37, "MARTIN", "Thomas", { club: "Triathlon Club Nantais", participations: 17 })],
      conflicts: [],
      clubs: [{ club: "Vendôme Triathlon", club_key: "vendometriathlon", results: 6 }],
    },
  ],
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <AthleteIdentityReviewTable />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
});

describe("AthleteIdentityReviewTable", () => {
  it("rend chaque cas avec son motif, ses fiches et ses épreuves en conflit", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const cartes = await screen.findAllByRole("article");
    expect(cartes).toHaveLength(2);
    expect(within(cartes[0]).getByRole("heading", { level: 2, name: /MARTIN Thomas/ })).toBeInTheDocument();
    expect(within(cartes[0]).getByText(/1 épreuve en conflit/)).toBeInTheDocument();
    expect(within(cartes[0]).getByText("Deux dossards sur une même épreuve")).toBeInTheDocument();
    expect(within(cartes[0]).getByRole("link", { name: /MARTIN Thomas/ })).toHaveAttribute("href", "/athletes/7");
    expect(within(cartes[0]).getByText(/IRONMAN Tours/)).toBeInTheDocument();
    expect(within(cartes[0]).getByText(/2348/)).toBeInTheDocument();
    expect(within(cartes[0]).getByText(/1715/)).toBeInTheDocument();
  });

  it("un cas à une fiche s'écarte sans se fusionner, et se règle aussi sur la fiche", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const [unique, paire] = await screen.findAllByRole("article");
    expect(within(unique).getByRole("button", { name: "Écarter le cas de MARTIN Thomas" })).toBeInTheDocument();
    expect(within(unique).queryByRole("button", { name: /fusionner/i })).not.toBeInTheDocument();
    expect(within(unique).getByText(/deux personnes/i)).toBeInTheDocument();
    expect(within(paire).getByRole("button", { name: "Écarter la paire DUPONT Jean et JEAN Dupont" })).toBeInTheDocument();
    expect(within(paire).getByRole("button", { name: "Fusionner DUPONT Jean et JEAN Dupont" })).toBeInTheDocument();
  });

  it("écarter une paire demande confirmation puis l'envoie", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(CAS);
    ignoreIdentityPair.mockResolvedValue({ athlete_id_a: 10, athlete_id_b: 11, ignored_at: "2026-10-02T10:00:00Z" });
    afficher();

    const [, paire] = await screen.findAllByRole("article");
    await userEvent.click(within(paire).getByRole("button", { name: /écarter/i }));
    await confirmerDansLeDialog("Écarter");

    expect(ignoreIdentityPair).toHaveBeenCalledWith(10, 11);
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("écarter un cas à une fiche demande confirmation, dit que les résultats restent, puis l'envoie (#1252)", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(CAS);
    dismissIdentityCase.mockResolvedValue({ athlete_id: 7, reason: "same_course_bibs", dismissed_at: "2026-10-08T10:00:00Z" });
    afficher();

    const [unique] = await screen.findAllByRole("article");
    await userEvent.click(within(unique).getByRole("button", { name: "Écarter le cas de MARTIN Thomas" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/aucun résultat n'est modifié/i)).toBeInTheDocument();
    await confirmerDansLeDialog("Écarter");

    expect(dismissIdentityCase).toHaveBeenCalledWith(7, "same_course_bibs");
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("sans `athletes:read`, la fusion n'est pas offerte : la recherche de fiches lui manque", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const [, paire] = await screen.findAllByRole("article");
    expect(within(paire).getByRole("button", { name: /écarter/i })).toBeInTheDocument();
    expect(within(paire).queryByRole("button", { name: /fusionner/i })).not.toBeInTheDocument();
  });

  it("une liste vide le dit, un refus aussi", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listIdentityReview.mockResolvedValue({ candidates: [] });
    const { unmount } = afficher();
    expect(await screen.findByText(/aucun cas d'identité/i)).toBeInTheDocument();
    unmount();

    listIdentityReview.mockRejectedValue(new ApiError(403, "Forbidden"));
    afficher();
    expect(await screen.findByText(/ne permet pas de consulter les cas d'identité/i)).toBeInTheDocument();
  });

  it("un cas multi-club liste ses clubs et confirme l'un d'eux", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(MULTI);
    confirmIdentityClub.mockResolvedValue({ athlete_id: 37, club_key: "vendometriathlon", confirmed_at: "2026-10-06T10:00:00Z" });
    afficher();

    const [carte] = await screen.findAllByRole("article");
    expect(within(carte).getByText(/Vendôme Triathlon · 6 résultats/)).toBeInTheDocument();
    expect(within(carte).getByText(/séparez/i)).toBeInTheDocument();
    await userEvent.click(within(carte).getByRole("button", { name: "Confirmer Vendôme Triathlon pour MARTIN Thomas" }));
    await confirmerDansLeDialog("Confirmer");

    expect(confirmIdentityClub).toHaveBeenCalledWith(37, "vendometriathlon");
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("un refus de l'API s'affiche en toast", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
    listIdentityReview.mockResolvedValue(MULTI);
    confirmIdentityClub.mockRejectedValue(new Error("Ce club est déjà confirmé pour cette fiche."));
    afficher();

    const [carte] = await screen.findAllByRole("article");
    await userEvent.click(within(carte).getByRole("button", { name: /Confirmer Vendôme Triathlon/ }));
    await confirmerDansLeDialog("Confirmer");

    expect(toastError).toHaveBeenCalledWith("Ce club est déjà confirmé pour cette fiche.");
  });
});

const ALL_POWERS = ["athletes:write", "athletes:read", "participations:reassign", "participations:delete"];

const result = (id: number, athleteId: number, club: string) =>
  ({
    id, club, athlete: { id: athleteId }, course: { id: id * 10, name: `Course ${id}`, event_date: "2025-06-01" },
  }) as unknown as Participation;

const pair = (reason: IdentityReviewCandidate["reason"], label: string): IdentityReviewList => ({
  candidates: [
    {
      reason, reason_label: label, athletes: [FICHE(10, "DUPONT", "Jean"), FICHE(11, "JEAN", "Dupont")],
      conflicts: [], clubs: [],
    },
  ],
});

describe("AthleteIdentityReviewTable : gestes et aide par motif (#1241)", () => {
  it("chaque carte renvoie vers la section du guide admin", async () => {
    getSession.mockResolvedValue(session(ALL_POWERS));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const cards = await screen.findAllByRole("article");
    for (const card of cards) {
      expect(within(card).getByRole("link", { name: /aide/i })).toHaveAttribute("href", "/admin/guide#identites");
    }
  });

  it("same_course_bibs : chaque ligne en conflit se rattache, se supprime ou se sépare, sans rien lire d'avance", async () => {
    getSession.mockResolvedValue(session(ALL_POWERS));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const [card] = await screen.findAllByRole("article");
    expect(within(card).getByText(/ce sont deux personnes/i)).toBeInTheDocument();
    for (const bib of ["2348", "1715"]) {
      expect(
        within(card).getByRole("button", { name: new RegExp(`Rattacher le résultat .*dossard ${bib}`) }),
      ).toBeInTheDocument();
      expect(
        within(card).getByRole("button", { name: new RegExp(`Supprimer le résultat .*dossard ${bib}`) }),
      ).toBeInTheDocument();
    }
    expect(await within(card).findAllByRole("button", { name: /Séparer le résultat/ })).toHaveLength(2);
    expect(getAthlete).not.toHaveBeenCalled();
  });

  it("same_course_bibs : séparer une ligne lit la fiche, la coche d'avance et reste sur la revue", async () => {
    getSession.mockResolvedValue(session(ALL_POWERS));
    listIdentityReview.mockResolvedValue(CAS);
    getAthlete.mockResolvedValue({ participations: [result(1, 7, "TCN"), result(2, 7, "TCN")] });
    detachParticipations.mockResolvedValue({ id: 99 });
    afficher();

    const [card] = await screen.findAllByRole("article");
    await userEvent.click(await within(card).findByRole("button", { name: /Séparer le résultat .*dossard 1715/ }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByRole("checkbox", { name: /Course 2/ })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: /Course 1/ })).not.toBeChecked();
    expect(getAthlete).toHaveBeenCalledWith(7);
    await userEvent.click(within(dialog).getByRole("button", { name: "Séparer vers une nouvelle fiche" }));
    await confirmerDansLeDialog("Séparer");

    await vi.waitFor(() => expect(detachParticipations).toHaveBeenCalledWith(7, [2]));
    expect(push).not.toHaveBeenCalled();
  });

  it("same_course_bibs : sans les pouvoirs sur les résultats, aucune action de ligne", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listIdentityReview.mockResolvedValue(CAS);
    afficher();

    const [card] = await screen.findAllByRole("article");
    expect(within(card).queryByRole("button", { name: /rattacher|supprimer|séparer/i })).not.toBeInTheDocument();
  });

  it("multi_club : séparer des résultats est offert à côté de la confirmation, la fiche n'est lue qu'à l'ouverture", async () => {
    getSession.mockResolvedValue(session(ALL_POWERS));
    listIdentityReview.mockResolvedValue(MULTI);
    getAthlete.mockResolvedValue({
      participations: [result(1, 37, "TCN"), result(2, 37, "Vendôme Triathlon")],
    });
    afficher();

    const [card] = await screen.findAllByRole("article");
    const detach = await within(card).findByRole("button", { name: "Séparer des résultats de MARTIN Thomas" });
    expect(within(card).getByRole("button", { name: /Confirmer Vendôme Triathlon/ })).toBeInTheDocument();
    expect(getAthlete).not.toHaveBeenCalled();

    await userEvent.click(detach);
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByRole("checkbox", { name: /Vendôme Triathlon/ })).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledWith(37);
  });

  it("multi_club : sans participations:reassign, seule la confirmation reste", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    listIdentityReview.mockResolvedValue(MULTI);
    afficher();

    const [card] = await screen.findAllByRole("article");
    expect(within(card).getByRole("button", { name: /Confirmer Vendôme Triathlon/ })).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /séparer/i })).not.toBeInTheDocument();
  });

  it.each([
    ["swapped", "Nom et prénom inversés", /inversez/i],
    ["concatenated", "Nom complet face à une fiche découpée", /redécoupez/i],
  ] as const)("%s : chaque fiche se corrige, la paire s'écarte ou se fusionne une seule fois", async (reason, label, help) => {
    getSession.mockResolvedValue(session(ALL_POWERS));
    listIdentityReview.mockResolvedValue(pair(reason, label));
    afficher();

    const [card] = await screen.findAllByRole("article");
    expect(within(card).getByText(help)).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Corriger la fiche de Jean DUPONT" })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Corriger la fiche de Dupont JEAN" })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: /écarter/i })).toBeInTheDocument();
    expect(within(card).getAllByRole("button", { name: /fusionner/i })).toHaveLength(1);
  });

  it("club_homonym : écarter ou fusionner, sans correction de fiche", async () => {
    getSession.mockResolvedValue(session(ALL_POWERS));
    listIdentityReview.mockResolvedValue(pair("club_homonym", "Homonymes, dont un du club"));
    afficher();

    const [card] = await screen.findAllByRole("article");
    expect(within(card).getByRole("button", { name: /écarter/i })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: /fusionner/i })).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /corriger/i })).not.toBeInTheDocument();
  });

  it("alias_collision : la carte renvoie vers les variantes de la fiche qui porte la graphie", async () => {
    getSession.mockResolvedValue(session(ALL_POWERS));
    listIdentityReview.mockResolvedValue(pair("alias_collision", "Fiche recréée sur une graphie fusionnée"));
    afficher();

    const [card] = await screen.findAllByRole("article");
    expect(within(card).getByRole("link", { name: "Voir les variantes de DUPONT Jean" })).toHaveAttribute(
      "href",
      "/athletes/10#variantes",
    );
    expect(within(card).getByRole("button", { name: /écarter/i })).toBeInTheDocument();
  });
});
