import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { CourseBrief, SessionUser } from "@/lib/types";

const { getCourse, getAthleteAdmin, getSession } = vi.hoisted(() => ({
  getCourse: vi.fn(),
  getAthleteAdmin: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getCourse, getAthleteAdmin, getSession } };
});

import { CourseParticipationsDialog } from "./CourseParticipationsDialog";

const EPREUVE: CourseBrief = {
  id: 12,
  name: "Triathlon de Nantes",
  event_date: "2026-05-17",
  event_type: "triathlon-m",
  provider: "klikego",
  source_url: "https://klikego.com/nantes",
  is_relay: false,
};

const DETAIL = {
  course: EPREUVE,
  participations: [
    {
      id: 7,
      athlete: { id: 1, nom: "J. DUPONT", prenom: "", gender: "M", club: "TCN" },
      course: EPREUVE,
      bib_number: "42",
      total_time: "01:23:45",
      status: "finisher",
    },
  ],
  total: 1,
  page: 1,
  page_size: 50,
};

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
    groups: [],
  };
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CourseParticipationsDialog course={EPREUVE} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe("CourseParticipationsDialog", () => {
  beforeEach(() => {
    getCourse.mockReset();
    getAthleteAdmin.mockReset();
    getSession.mockReset();
    getCourse.mockResolvedValue(DETAIL);
    getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
  });

  it("liste les résultats de l'épreuve", async () => {
    afficher();

    expect(await screen.findByText(/J\. DUPONT/)).toBeInTheDocument();
  });

  it("filtre côté serveur plutôt que d'afficher 50 lignes muettes", async () => {
    afficher();
    await screen.findByText(/J\. DUPONT/);

    await userEvent.type(screen.getByRole("searchbox"), "dupont");

    // Sur une épreuve de 1811 participants, sans ce filtre le résultat cherché
    // est presque toujours hors de la première tranche.
    await waitFor(() =>
      expect(getCourse).toHaveBeenCalledWith(12, expect.objectContaining({ q: "dupont" })),
    );
  });

  it("charge la fiche complète avant d'ouvrir l'édition d'un coureur", async () => {
    getAthleteAdmin.mockResolvedValue({
      id: 1,
      nom: "J. DUPONT",
      prenom: "",
      birth_date: "1988-03-02",
      gender: "M",
      club: "TCN",
      participations: 3,
    });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /corriger le coureur/i }));

    // Le résultat ne porte qu'un `AthleteBrief` : ouvrir l'édition avec lui
    // afficherait une date de naissance vide, et l'enregistrer l'effacerait.
    await waitFor(() => expect(getAthleteAdmin).toHaveBeenCalledWith(1));
    expect(await screen.findByLabelText(/naissance/i)).toHaveValue("1988-03-02");
  });

  it("garde la liste affichée le temps que la fiche charge", async () => {
    let livrer: (fiche: unknown) => void = () => {};
    getAthleteAdmin.mockReturnValue(new Promise((resolve) => (livrer = resolve)));

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /corriger le coureur/i }));

    // Fermer la liste dès le clic laisserait l'écran sans aucune modale tant
    // que la fiche n'est pas arrivée : un trou visible, et définitif si elle
    // n'arrive jamais.
    expect(screen.getByText(/J\. DUPONT/)).toBeInTheDocument();

    livrer({
      id: 1,
      nom: "J. DUPONT",
      prenom: "",
      birth_date: "1988-03-02",
      gender: "M",
      club: "TCN",
      participations: 3,
    });
    expect(await screen.findByLabelText(/naissance/i)).toBeInTheDocument();
  });

  it("ne laisse pas l'écran dans un cul-de-sac si la fiche est refusée", async () => {
    // Composition de rôle légale : `athletes:write` sans `athletes:read`.
    getSession.mockResolvedValue(session(["athletes:write"]));
    getAthleteAdmin.mockRejectedValue(new ApiError(403, "Interdit"));

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /corriger le coureur/i }));

    expect(await screen.findByText(/n'a pas pu être chargée/i)).toBeInTheDocument();
    // La liste des résultats reste consultable — elle ne disparaît pas derrière
    // une modale qui ne s'ouvrira jamais.
    expect(screen.getByText(/J\. DUPONT/)).toBeInTheDocument();
  });

  it("cache les gestes que la session ne permet pas", async () => {
    getSession.mockResolvedValue(session([]));

    afficher();
    await screen.findByText(/J\. DUPONT/);

    expect(screen.queryByRole("button", { name: /rattacher/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /corriger le coureur/i }),
    ).not.toBeInTheDocument();
  });

  it("n'offre pas le rattachement sans `athletes:read` (#439, FR-020)", async () => {
    // Bug latent : le sélecteur de la réattribution appelle
    // `GET /admin/athletes?search=`, gardée par `athletes:read`. Annoncé sur le
    // seul `participations:reassign`, le geste s'ouvre sur une liste vide qui ne
    // se remplira jamais — un 403 muet. La visibilité se règle par **geste**,
    // pas par écran.
    getSession.mockResolvedValue(session(["participations:reassign"]));

    afficher();
    await screen.findByText(/J\. DUPONT/);

    expect(screen.queryByRole("button", { name: /rattacher/i })).not.toBeInTheDocument();
  });

  it("offre le rattachement au porteur des deux pouvoirs (US4-AC3)", async () => {
    getSession.mockResolvedValue(session(["participations:reassign", "athletes:read"]));

    afficher();
    await screen.findByText(/J\. DUPONT/);

    expect(await screen.findByRole("button", { name: /rattacher/i })).toBeInTheDocument();
  });
});
