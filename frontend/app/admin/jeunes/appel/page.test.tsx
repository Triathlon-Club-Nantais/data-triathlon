import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { TrainingSession, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { replace, listTrainingSessions, createTrainingSession, getSession } = vi.hoisted(() => ({
  replace: vi.fn(),
  listTrainingSessions: vi.fn(),
  createTrainingSession: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/admin/jeunes/appel",
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listTrainingSessions, createTrainingSession, getSession } };
});

import AdminJeuneAppelDuJourPage from "./page";

const AUJOURDHUI = "2026-09-24";

function seance(id: number, champs: Partial<TrainingSession> = {}): TrainingSession {
  return {
    id,
    date: AUJOURDHUI,
    start_time: null,
    location: null,
    session_type: null,
    note: "",
    participant_count: 0,
    ...champs,
  };
}

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "encadrant@exemple.fr",
    display_name: "Encadrant",
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
      <AdminJeuneAppelDuJourPage />
    </QueryClientProvider>,
  );
}

describe("AdminJeuneAppelDuJourPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 24, 16, 0));
    getSession.mockResolvedValue(session(["jeunes:read", "jeunes:write"]));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("ouvre directement l'appel de l'unique séance du jour", async () => {
    listTrainingSessions.mockResolvedValue([seance(7), seance(8, { date: "2026-09-25" })]);

    afficher();

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/admin/jeunes/appel/7"));
  });

  it("fait choisir la séance quand il y en a plusieurs le même jour", async () => {
    listTrainingSessions.mockResolvedValue([
      seance(7, { start_time: "10:00:00", session_type: "Natation" }),
      seance(8, { start_time: "17:00:00", session_type: "Course" }),
    ]);

    afficher();

    const natation = await screen.findByRole("link", { name: /10:00.*natation/i });
    const course = screen.getByRole("link", { name: /17:00.*course/i });
    expect(natation).toHaveAttribute("href", "/admin/jeunes/appel/7");
    expect(course).toHaveAttribute("href", "/admin/jeunes/appel/8");
    expect(replace).not.toHaveBeenCalled();
  });

  it("propose de créer la séance du jour à un porteur de jeunes:write", async () => {
    listTrainingSessions.mockResolvedValue([]);

    afficher();

    expect(
      await screen.findByRole("button", { name: /créer la séance du jour/i }),
    ).toBeInTheDocument();
  });

  it("ne propose pas de créer la séance sans jeunes:write", async () => {
    getSession.mockResolvedValue(session(["jeunes:read"]));
    listTrainingSessions.mockResolvedValue([]);

    afficher();

    await screen.findByText(/aucune séance aujourd'hui/i);
    expect(
      screen.queryByRole("button", { name: /créer la séance du jour/i }),
    ).not.toBeInTheDocument();
  });
});
