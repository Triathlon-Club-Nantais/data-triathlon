import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { TrainingSessionDetail, Profile, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const {
  getTrainingSession,
  listProfiles,
  addTrainingParticipant,
  setTrainingParticipantPresence,
  getSession,
} = vi.hoisted(() => ({
  getTrainingSession: vi.fn(),
  listProfiles: vi.fn(),
  addTrainingParticipant: vi.fn(),
  setTrainingParticipantPresence: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getTrainingSession,
      listProfiles,
      addTrainingParticipant,
      setTrainingParticipantPresence,
      getSession,
    },
  };
});

import { AppelPresence } from "./AppelPresence";

const ALIX: Profile = {
  id: 42,
  organisation_id: 1,
  first_name: "Alix",
  last_name: "Martin",
  birth_date: null,
  created_at: "2026-01-01T00:00:00Z",
};

const ZOE: Profile = {
  id: 43,
  organisation_id: 1,
  first_name: "Zoé",
  last_name: "Roux",
  birth_date: null,
  created_at: "2026-01-01T00:00:00Z",
};

const DETAIL_UN_PARTICIPANT: TrainingSessionDetail = {
  id: 1,
  date: "2026-09-20",
  start_time: null,
  location: null,
  session_type: null,
  note: "",
  participant_count: 1,
  participants: [{ profile_id: 42, present: null, created_at: "2026-09-15T10:00:00Z" }],
};

const DETAIL_VIDE: TrainingSessionDetail = { ...DETAIL_UN_PARTICIPANT, participant_count: 0, participants: [] };

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
      <AppelPresence sessionId={1} />
    </QueryClientProvider>,
  );
}

describe("AppelPresence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(AVEC_ECRITURE);
    listProfiles.mockResolvedValue([ALIX, ZOE]);
  });

  it("liste les jeunes inscrits avec leur nom", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_UN_PARTICIPANT);

    afficher();

    expect(await screen.findByText("Alix Martin")).toBeInTheDocument();
  });

  it("pointe un jeune présent au clic", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_UN_PARTICIPANT);
    setTrainingParticipantPresence.mockResolvedValue(DETAIL_UN_PARTICIPANT);

    afficher();
    await screen.findByText("Alix Martin");
    await userEvent.click(screen.getByRole("button", { name: /présent/i }));

    expect(setTrainingParticipantPresence).toHaveBeenCalledWith(1, 42, true);
  });

  it("pointe un jeune absent au clic", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_UN_PARTICIPANT);
    setTrainingParticipantPresence.mockResolvedValue(DETAIL_UN_PARTICIPANT);

    afficher();
    await screen.findByText("Alix Martin");
    await userEvent.click(screen.getByRole("button", { name: /absent/i }));

    expect(setTrainingParticipantPresence).toHaveBeenCalledWith(1, 42, false);
  });

  it("ajoute un jeune non inscrit et le pointe présent en un geste", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_VIDE);
    addTrainingParticipant.mockResolvedValue(DETAIL_UN_PARTICIPANT);

    afficher();
    await screen.findByLabelText(/ajouter un jeune/i);
    await userEvent.selectOptions(screen.getByLabelText(/ajouter un jeune/i), "42");

    expect(addTrainingParticipant).toHaveBeenCalledWith(1, 42, true);
  });

  it("n'affiche aucun contrôle d'écriture sans jeunes:write", async () => {
    getSession.mockResolvedValue(LECTURE_SEULE);
    getTrainingSession.mockResolvedValue(DETAIL_UN_PARTICIPANT);

    afficher();

    await screen.findByText("Alix Martin");
    expect(screen.queryByRole("button", { name: /présent/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /absent/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/ajouter un jeune/i)).not.toBeInTheDocument();
  });

  it("affiche un état vide explicite sans aucun jeune inscrit", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_VIDE);

    afficher();

    expect(await screen.findByText(/aucun jeune inscrit/i)).toBeInTheDocument();
  });

  it("porte un lien vers le profil de chaque jeune inscrit (FR-010)", async () => {
    getTrainingSession.mockResolvedValue(DETAIL_UN_PARTICIPANT);

    afficher();
    await screen.findByText("Alix Martin");

    expect(screen.getByRole("link", { name: /voir le profil/i })).toHaveAttribute(
      "href",
      "/admin/jeunes/42",
    );
  });

  it("bascule vers l'appel de fin sans écrire aucune donnée", async () => {
    const detail: TrainingSessionDetail = {
      ...DETAIL_UN_PARTICIPANT,
      participants: [{ profile_id: 42, present: true, created_at: "2026-09-15T10:00:00Z" }],
    };
    getTrainingSession.mockResolvedValue(detail);

    afficher();
    await screen.findByText("Alix Martin");
    await userEvent.click(screen.getByRole("tab", { name: /appel de fin/i }));

    expect(await screen.findByText(/1 jeune restant/i)).toBeInTheDocument();
    expect(setTrainingParticipantPresence).not.toHaveBeenCalled();
  });
});
