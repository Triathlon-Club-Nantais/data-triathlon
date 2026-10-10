import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { Profile, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { listProfiles, createProfile, getSession } = vi.hoisted(() => ({
  listProfiles: vi.fn(),
  createProfile: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listProfiles, createProfile, getSession },
  };
});

import { ApiError } from "@/lib/api/client";
import { ProfilesList } from "./ProfilesList";

const ALIX: Profile = {
  id: 1,
  organisation_id: 1,
  first_name: "Alix",
  last_name: "Martin",
  birth_date: "2015-04-12",
  category: "Pupille",
  membership_ended_on: null,
  created_at: "2026-01-01T00:00:00Z",
};

const AVEC_ECRITURE: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["jeunes:read", "jeunes:write"],
  roles: [],
  groups: [],
  can_administer: true,
};

const LECTURE_SEULE: SessionUser = { ...AVEC_ECRITURE, permissions: ["jeunes:read"] };

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ProfilesList />
    </QueryClientProvider>,
  );
}

describe("ProfilesList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(AVEC_ECRITURE);
  });

  afterEach(() => focusManager.setFocused(undefined));

  it("ne prend pas une relance suspendue pour une liste vide (#1290)", async () => {
    // Backend endormi : le premier essai échoue, et React Query suspend la
    // relance tant que l'onglet n'a pas le focus.
    focusManager.setFocused(false);
    listProfiles.mockRejectedValue(new ApiError(503, "Service indisponible"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: 1, retryDelay: 0 } } });
    render(
      <QueryClientProvider client={client}>
        <ProfilesList />
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(client.getQueryCache().find({ queryKey: ["admin-profiles"] })?.state.fetchStatus).toBe(
        "paused",
      ),
    );
    expect(screen.queryByText(/aucun jeune référencé/i)).not.toBeInTheDocument();
  });

  it("liste les profils existants", async () => {
    listProfiles.mockResolvedValue([ALIX]);

    afficher();

    expect(await screen.findByText("Alix Martin")).toBeInTheDocument();
  });

  it("affiche un état vide quand aucun profil n'existe", async () => {
    listProfiles.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun (profil|jeune)/i)).toBeInTheDocument();
  });

  it("propose le formulaire de création à un porteur de jeunes:write", async () => {
    listProfiles.mockResolvedValue([]);

    afficher();

    expect(await screen.findByRole("button", { name: /créer/i })).toBeInTheDocument();
  });

  it("ne propose aucun formulaire de création sans jeunes:write", async () => {
    getSession.mockResolvedValue(LECTURE_SEULE);
    listProfiles.mockResolvedValue([]);

    afficher();

    await screen.findByText(/aucun (profil|jeune)/i);
    expect(screen.queryByRole("button", { name: /créer/i })).not.toBeInTheDocument();
  });

  it("crée un profil depuis le formulaire", async () => {
    listProfiles.mockResolvedValue([]);
    createProfile.mockResolvedValue({ ...ALIX, log_entries: [] });
    const utilisateur = userEvent.setup();

    afficher();
    await screen.findByRole("button", { name: /créer/i });
    await utilisateur.type(screen.getByLabelText(/prénom/i), "Alix");
    await utilisateur.type(screen.getByLabelText(/^nom/i), "Martin");
    await utilisateur.click(screen.getByRole("button", { name: /créer/i }));

    await waitFor(() =>
      expect(createProfile).toHaveBeenCalledWith(
        expect.objectContaining({ first_name: "Alix", last_name: "Martin" }),
      ),
    );
  });

  it("crée un profil avec sa date de naissance", async () => {
    listProfiles.mockResolvedValue([]);
    createProfile.mockResolvedValue({ ...ALIX, log_entries: [] });
    const utilisateur = userEvent.setup();

    afficher();
    await screen.findByRole("button", { name: /créer/i });
    await utilisateur.type(screen.getByLabelText(/prénom/i), "Alix");
    await utilisateur.type(screen.getByLabelText(/^nom/i), "Martin");
    await utilisateur.type(screen.getByLabelText(/date de naissance/i), "2015-04-12");
    await utilisateur.click(screen.getByRole("button", { name: /créer/i }));

    await waitFor(() =>
      expect(createProfile).toHaveBeenCalledWith({
        first_name: "Alix",
        last_name: "Martin",
        birth_date: "2015-04-12",
      }),
    );
  });

  it("n'envoie aucune date de naissance laissée vide", async () => {
    listProfiles.mockResolvedValue([]);
    createProfile.mockResolvedValue({ ...ALIX, log_entries: [] });
    const utilisateur = userEvent.setup();

    afficher();
    await screen.findByRole("button", { name: /créer/i });
    await utilisateur.type(screen.getByLabelText(/prénom/i), "Alix");
    await utilisateur.type(screen.getByLabelText(/^nom/i), "Martin");
    await utilisateur.click(screen.getByRole("button", { name: /créer/i }));

    await waitFor(() =>
      expect(createProfile).toHaveBeenCalledWith({ first_name: "Alix", last_name: "Martin" }),
    );
  });
});
