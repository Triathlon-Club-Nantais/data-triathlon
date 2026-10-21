import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

import { ApiError } from "@/lib/api/client";
import { AppelPresence } from "./AppelPresence";

const ALIX: Profile = {
  id: 42,
  organisation_id: 1,
  first_name: "Alix",
  last_name: "Martin",
  birth_date: null,
  category: null,
  membership_ended_on: null,
  created_at: "2026-01-01T00:00:00Z",
};

const ZOE: Profile = {
  id: 43,
  organisation_id: 1,
  first_name: "Zoé",
  last_name: "Roux",
  birth_date: null,
  category: null,
  membership_ended_on: null,
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
  group_ids: [],
  recurrence_id: null,
  detached: false,
  participants: [{ profile_id: 42, present: null, added_manually: true, category: null, created_at: "2026-09-15T10:00:00Z", emergency_contact: null }],
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
  is_member: false,
  athlete: null,
  athlete_claim: null,
  member_request: null,
  can_administer: false,
  can_supervise: true,
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

  afterEach(() => focusManager.setFocused(undefined));

  it("ne prend pas une relance suspendue pour une absence de données (#1290)", async () => {
    // Backend endormi : le premier essai échoue, et React Query suspend la
    // relance tant que l'onglet n'a pas le focus.
    focusManager.setFocused(false);
    getTrainingSession.mockRejectedValue(new ApiError(503, "Service indisponible"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: 1, retryDelay: 0 } } });
    render(
      <QueryClientProvider client={client}>
        <AppelPresence sessionId={1} />
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(client.getQueryCache().find({ queryKey: ["admin-training-session", 1] })?.state.fetchStatus).toBe("paused"),
    );
    expect(screen.queryByText("Séance introuvable")).not.toBeInTheDocument();
  });

  it("affiche la catégorie FFTri de chaque inscrit (#1291)", async () => {
    getTrainingSession.mockResolvedValue({
      ...DETAIL_UN_PARTICIPANT,
      participants: [{ ...DETAIL_UN_PARTICIPANT.participants[0], category: "Benjamin" }],
    });

    afficher();

    expect(await screen.findByText("Benjamin")).toBeInTheDocument();
  });

  it("affiche sur la carte le contact d'urgence, numéro composable (#1405)", async () => {
    getTrainingSession.mockResolvedValue({
      ...DETAIL_UN_PARTICIPANT,
      participants: [{ ...DETAIL_UN_PARTICIPANT.participants[0], emergency_contact: "Mère 06 12 34 56 78" }],
    });

    afficher();

    const lien = await screen.findByRole("link", { name: "06 12 34 56 78" });
    expect(lien).toHaveAttribute("href", "tel:0612345678");
    // Numéro d'un parent de mineur : hors de l'autocapture PostHog (RGPD).
    expect(lien).toHaveClass("ph-no-capture");
    expect(screen.getByText(/Mère/)).toBeInTheDocument();
  });

  it.each(["", null])("n'affiche rien pour un contact d'urgence absent (%j)", async (contact) => {
    getTrainingSession.mockResolvedValue({
      ...DETAIL_UN_PARTICIPANT,
      participants: [{ ...DETAIL_UN_PARTICIPANT.participants[0], emergency_contact: contact }],
    });

    afficher();

    expect(await screen.findByText("Alix Martin")).toBeInTheDocument();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
    expect(screen.queryByText(/Contact d'urgence/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^0/ })).not.toBeInTheDocument();
  });

  it("dit qu'une séance absente est introuvable", async () => {
    getTrainingSession.mockRejectedValue(new ApiError(404, "Cet entraînement n'existe pas."));

    afficher();

    expect(await screen.findByText("Séance introuvable")).toBeInTheDocument();
  });

  it("nomme la séance par sa date, son heure et son lieu", async () => {
    getTrainingSession.mockResolvedValue({
      ...DETAIL_UN_PARTICIPANT,
      start_time: "18:00:00",
      location: "Base nautique",
    });

    afficher();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Appel du 20/09/2026" }),
    ).toBeInTheDocument();
    expect(screen.getByText("18:00, Base nautique")).toBeInTheDocument();
  });

  it("garde un titre d'appel tant que la séance n'est pas chargée", () => {
    getTrainingSession.mockReturnValue(new Promise(() => {}));

    afficher();

    expect(screen.getByRole("heading", { level: 1, name: "Appel" })).toBeInTheDocument();
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

  it("annonce l'état pointé de chaque paire Présent / Absent (#1013)", async () => {
    getTrainingSession.mockResolvedValue({
      ...DETAIL_UN_PARTICIPANT,
      participants: [{ ...DETAIL_UN_PARTICIPANT.participants[0], present: true }],
    });

    afficher();
    await screen.findByText("Alix Martin");

    const paire = screen.getByRole("group", { name: "Présence de Alix Martin" });
    expect(within(paire).getByRole("button", { name: "Présent" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(paire).getByRole("button", { name: "Absent" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
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
      "/encadrement/jeunes/42",
    );
  });

  it("compte les présents et les absents, sur les deux appels", async () => {
    getTrainingSession.mockResolvedValue({
      ...DETAIL_UN_PARTICIPANT,
      participant_count: 3,
      group_ids: [],
      recurrence_id: null,
      detached: false,
      participants: [
        { profile_id: 42, present: true, added_manually: true, category: null, created_at: "2026-09-15T10:00:00Z", emergency_contact: null },
        { profile_id: 43, present: false, added_manually: true, category: null, created_at: "2026-09-15T10:00:00Z", emergency_contact: null },
        { profile_id: 44, present: null, added_manually: true, category: null, created_at: "2026-09-15T10:00:00Z", emergency_contact: null },
      ],
    });

    afficher();

    expect(await screen.findByText("1 présent sur 3, 1 absent, 1 à pointer")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /appel de fin/i }));
    expect(screen.getByText("1 présent sur 3, 1 absent, 1 à pointer")).toBeInTheDocument();
  });

  it("accorde le compteur au pluriel et tait les jeunes à pointer quand il n'y en a plus", async () => {
    getTrainingSession.mockResolvedValue({
      ...DETAIL_UN_PARTICIPANT,
      participant_count: 2,
      group_ids: [],
      recurrence_id: null,
      detached: false,
      participants: [
        { profile_id: 42, present: true, added_manually: true, category: null, created_at: "2026-09-15T10:00:00Z", emergency_contact: null },
        { profile_id: 43, present: true, added_manually: true, category: null, created_at: "2026-09-15T10:00:00Z", emergency_contact: null },
      ],
    });

    afficher();

    expect(await screen.findByText("2 présents sur 2, 0 absent")).toBeInTheDocument();
  });

  describe("tri et recherche (#1610)", () => {
    const profil = (id: number, first_name: string, last_name: string): Profile => ({ ...ALIX, id, first_name, last_name });
    const inscrit = (profile_id: number, present: boolean | null = null) => ({
      profile_id,
      present,
      added_manually: true,
      category: null,
      created_at: "2026-09-15T10:00:00Z",
      emergency_contact: null,
    });

    beforeEach(() => {
      listProfiles.mockResolvedValue([ALIX, ZOE, profil(44, "Paul", "Dupont"), profil(45, "Léa", "écuyer")]);
      getTrainingSession.mockResolvedValue({
        ...DETAIL_UN_PARTICIPANT,
        participant_count: 4,
        participants: [inscrit(43, true), inscrit(42), inscrit(45), inscrit(44, false)],
      });
    });

    const ordre = () =>
      screen.getAllByRole("group", { name: /^Présence de / }).map((groupe) => groupe.getAttribute("aria-label"));

    it("trie les inscrits par nom puis prénom, sans accent ni casse, quel que soit l'ordre d'inscription", async () => {
      afficher();

      await screen.findByText("Zoé Roux");
      expect(ordre()).toEqual([
        "Présence de Paul Dupont",
        "Présence de Léa écuyer",
        "Présence de Alix Martin",
        "Présence de Zoé Roux",
      ]);
    });

    it("filtre sur le prénom sans accent, le compteur restant calculé sur tous les inscrits", async () => {
      afficher();

      await userEvent.type(await screen.findByLabelText("Rechercher un jeune"), "zoe");

      expect(ordre()).toEqual(["Présence de Zoé Roux"]);
      expect(screen.getByText("1 présent sur 4, 1 absent, 2 à pointer")).toBeInTheDocument();
    });

    it("dit qu'aucun inscrit ne correspond, sans le confondre avec une séance vide", async () => {
      afficher();

      await userEvent.type(await screen.findByLabelText("Rechercher un jeune"), "xyz");

      expect(screen.getByText("Aucun jeune ne correspond à « xyz ».")).toBeInTheDocument();
      expect(screen.queryByText("Aucun jeune inscrit")).not.toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: "Effacer la recherche" }));
      expect(ordre()).toHaveLength(4);
    });
  });

  it("bascule vers l'appel de fin sans écrire aucune donnée", async () => {
    const detail: TrainingSessionDetail = {
      ...DETAIL_UN_PARTICIPANT,
      participants: [{ profile_id: 42, present: true, added_manually: true, category: null, created_at: "2026-09-15T10:00:00Z", emergency_contact: null }],
    };
    getTrainingSession.mockResolvedValue(detail);

    afficher();
    await screen.findByText("Alix Martin");
    await userEvent.click(screen.getByRole("tab", { name: /appel de fin/i }));

    expect(await screen.findByText(/1 jeune restant/i)).toBeInTheDocument();
    expect(setTrainingParticipantPresence).not.toHaveBeenCalled();
  });
});
