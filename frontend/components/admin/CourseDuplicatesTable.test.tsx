import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { DuplicateCandidateList, SessionUser } from "@/lib/types";

const { listCourseDuplicates, getSession } = vi.hoisted(() => ({
  listCourseDuplicates: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listCourseDuplicates, getSession } };
});

import { CourseDuplicatesTable } from "./CourseDuplicatesTable";

const AVEC_DROIT: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  permissions: ["courses:sources", "courses:delete"],
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
} as unknown as SessionUser;

const SANS_SUPPRESSION: SessionUser = { ...AVEC_DROIT, permissions: ["courses:sources"] } as SessionUser;

const PAIRE: DuplicateCandidateList = {
  candidates: [
    {
      reason: "shared_event_id",
      reason_label: "Identifiant d'événement partagé",
      courses: [
        {
          id: 38, name: "Triathlon et SwimRun Mesquer-Quimiac 2026", event_date: "2026-06-13",
          event_type: "swimrun-s", is_relay: false, provider: "klikego",
          source_url: "https://klikego.com/x", total: 185, tcn_count: 3,
        },
        {
          id: 50, name: "Triathlon et SwimRun Mesquer-Quimiac 2026", event_date: "2026-06-13",
          event_type: "triathlon-s", is_relay: false, provider: "breizhchrono",
          source_url: "https://breizhchrono.com/x", total: 179, tcn_count: 3,
        },
      ],
    },
  ],
};

const MEME_URL: DuplicateCandidateList = {
  candidates: [
    {
      reason: "same_source_url",
      reason_label: "Même URL de source",
      courses: [
        {
          id: 38, name: "Mesquer", event_date: "2026-06-13", event_type: "swimrun-s",
          is_relay: false, provider: "klikego", source_url: "https://klikego.com/x",
          total: 185, tcn_count: 3,
        },
        {
          id: 39, name: "Mesquer", event_date: "2026-06-13", event_type: "triathlon-s",
          is_relay: false, provider: "klikego", source_url: "https://klikego.com/x",
          total: 60, tcn_count: 0,
        },
      ],
    },
  ],
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CourseDuplicatesTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CourseDuplicatesTable", () => {
  it("dit qu'il n'y a aucun doublon suspect sur une liste vide", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue({ candidates: [] });

    afficher();

    expect(await screen.findByText(/aucun doublon suspect/i)).toBeInTheDocument();
  });

  it("affiche la raison et les deux épreuves de chaque paire", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    expect(await screen.findByText(/identifiant d'événement partagé/i)).toBeInTheDocument();
    expect(screen.getByText(/klikego/i)).toBeInTheDocument();
    expect(screen.getByText(/breizh chrono/i)).toBeInTheDocument();
  });

  it("propose la fusion à un porteur de courses:delete", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    expect(await screen.findByRole("button", { name: /fusionner/i })).toBeInTheDocument();
  });

  it("ne propose aucune fusion sans courses:delete", async () => {
    getSession.mockResolvedValue(SANS_SUPPRESSION);
    listCourseDuplicates.mockResolvedValue(PAIRE);

    afficher();

    await screen.findByText(/identifiant d'événement partagé/i);
    expect(screen.queryByRole("button", { name: /fusionner/i })).not.toBeInTheDocument();
  });

  it("signale qu'une même URL se corrige plutôt qu'elle ne se fusionne", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockResolvedValue(MEME_URL);

    afficher();

    expect(await screen.findByText(/même url de source/i)).toBeInTheDocument();
    expect(screen.getByText(/correction du type d'épreuve/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403, et non « aucun doublon »", async () => {
    getSession.mockResolvedValue(AVEC_DROIT);
    listCourseDuplicates.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun doublon suspect/i)).not.toBeInTheDocument();
  });
});
