import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { Entrainement, EntrainementDetail, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { listEntrainements, getEntrainement, createEntrainement, getSession } = vi.hoisted(
  () => ({
    listEntrainements: vi.fn(),
    getEntrainement: vi.fn(),
    createEntrainement: vi.fn(),
    getSession: vi.fn(),
  }),
);

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listEntrainements, getEntrainement, createEntrainement, getSession },
  };
});

import { CalendrierEntrainements } from "./CalendrierEntrainements";

const SEANCE: Entrainement = {
  id: 1,
  date: "2026-09-20",
  heure_debut: "18:00:00",
  lieu: "Base nautique",
  type_seance: "Natation",
  participant_count: 2,
};

const SEANCE_SANS_CHAMPS: Entrainement = {
  id: 2,
  date: "2026-09-27",
  heure_debut: null,
  lieu: null,
  type_seance: null,
  participant_count: 0,
};

const DETAIL: EntrainementDetail = { ...SEANCE, participants: [] };

const AVEC_ECRITURE: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["jeunes:read", "jeunes:write"],
  roles: [],
  groups: [],
};

const LECTURE_SEULE: SessionUser = { ...AVEC_ECRITURE, permissions: ["jeunes:read"] };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CalendrierEntrainements />
    </QueryClientProvider>,
  );
}

describe("CalendrierEntrainements", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(AVEC_ECRITURE);
    getEntrainement.mockResolvedValue(DETAIL);
  });

  it("liste les entraînements triés, avec leur nombre d'inscrits", async () => {
    listEntrainements.mockResolvedValue([SEANCE]);

    afficher();

    expect(await screen.findByText("20/09/2026")).toBeInTheDocument();
    expect(screen.getByText("Base nautique")).toBeInTheDocument();
    expect(screen.getByText("Natation")).toBeInTheDocument();
    expect(screen.getByText(/2 inscrits/)).toBeInTheDocument();
  });

  it("n'affiche aucun texte vide pour les champs optionnels absents", async () => {
    listEntrainements.mockResolvedValue([SEANCE_SANS_CHAMPS]);

    afficher();

    expect(await screen.findByText("27/09/2026")).toBeInTheDocument();
    expect(screen.getByText("Lieu non renseigné")).toBeInTheDocument();
    expect(screen.getByText(/0 inscrit/)).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
    expect(screen.queryByText("null")).not.toBeInTheDocument();
  });

  it("dit « aucun entraînement » sur une liste vide", async () => {
    listEntrainements.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun entraînement/i)).toBeInTheDocument();
  });

  it("ne propose aucune commande d'écriture sans jeunes:write", async () => {
    getSession.mockResolvedValue(LECTURE_SEULE);
    listEntrainements.mockResolvedValue([SEANCE]);

    afficher();

    await screen.findByText("20/09/2026");
    expect(screen.queryByLabelText(/^date$/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /créer la séance/i })).not.toBeInTheDocument();
  });

  it("crée un entraînement à partir de sa date", async () => {
    listEntrainements.mockResolvedValue([]);
    createEntrainement.mockResolvedValue(DETAIL);

    afficher();
    await screen.findByText(/aucun entraînement/i);
    await userEvent.type(screen.getByLabelText(/^date$/i), "2026-09-20");
    await userEvent.click(screen.getByRole("button", { name: /créer la séance/i }));

    expect(createEntrainement).toHaveBeenCalledWith({
      date: "2026-09-20",
      heure_debut: null,
      lieu: null,
      type_seance: null,
    });
  });

  it("dit « accès refusé » sur un 403", async () => {
    listEntrainements.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });
});
