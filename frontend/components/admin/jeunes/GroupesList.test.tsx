import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Profile, SessionUser, TrainingGroupDetail } from "@/lib/types";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("sonner", () => ({ toast }));

const {
  listTrainingGroups,
  getTrainingGroup,
  createTrainingGroup,
  renameTrainingGroup,
  deleteTrainingGroup,
  addTrainingGroupMember,
  removeTrainingGroupMember,
  listProfiles,
  getSession,
} = vi.hoisted(() => ({
  listTrainingGroups: vi.fn(),
  getTrainingGroup: vi.fn(),
  createTrainingGroup: vi.fn(),
  renameTrainingGroup: vi.fn(),
  deleteTrainingGroup: vi.fn(),
  addTrainingGroupMember: vi.fn(),
  removeTrainingGroupMember: vi.fn(),
  listProfiles: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      listTrainingGroups,
      getTrainingGroup,
      createTrainingGroup,
      renameTrainingGroup,
      deleteTrainingGroup,
      addTrainingGroupMember,
      removeTrainingGroupMember,
      listProfiles,
      getSession,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { GroupesList } from "./GroupesList";

function profil(id: number, prenom: string, champs: Partial<Profile> = {}): Profile {
  return {
    id,
    organisation_id: 1,
    first_name: prenom,
    last_name: "Martin",
    birth_date: null,
    category: null,
    membership_ended_on: null,
    created_at: "2026-01-01T00:00:00Z",
    ...champs,
  };
}

const ALIX = profil(1, "Alix");
const ZOE = profil(2, "Zoé", { membership_ended_on: "2026-01-31" });
const GROUPE: TrainingGroupDetail = { id: 7, name: "Benjamins mercredi", members: [ALIX, ZOE] };

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

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <GroupesList />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

async function ouvrirLeGroupe() {
  await userEvent.click(await screen.findByRole("button", { name: /Benjamins mercredi/ }));
  return screen.findByRole("dialog");
}

describe("GroupesList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(AVEC_ECRITURE);
    listTrainingGroups.mockResolvedValue([{ id: 7, name: "Benjamins mercredi", member_count: 2 }]);
    getTrainingGroup.mockResolvedValue(GROUPE);
    listProfiles.mockResolvedValue([ALIX, ZOE, profil(3, "Noé")]);
  });

  it("liste les groupes avec leur nombre de membres", async () => {
    afficher();

    expect(await screen.findByText("Benjamins mercredi")).toBeInTheDocument();
    expect(screen.getByText("2 membres")).toBeInTheDocument();
  });

  it("distingue une erreur de chargement d'une liste vide", async () => {
    listTrainingGroups.mockRejectedValue(new ApiError(503, "Service indisponible"));

    afficher();

    await waitFor(() => expect(listTrainingGroups).toHaveBeenCalled());
    expect(await screen.findByText("Liste indisponible")).toBeInTheDocument();
    expect(screen.queryByText(/aucun groupe/i)).not.toBeInTheDocument();
  });

  it("annonce une liste vide", async () => {
    listTrainingGroups.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun groupe/i)).toBeInTheDocument();
  });

  it("crée un groupe", async () => {
    createTrainingGroup.mockResolvedValue({ id: 8, name: "Minimes", members: [] });
    afficher();

    await userEvent.type(await screen.findByLabelText("Nom du groupe"), "Minimes");
    await userEvent.click(screen.getByRole("button", { name: "Créer le groupe" }));

    await waitFor(() => expect(createTrainingGroup).toHaveBeenCalledWith("Minimes"));
  });

  it("affiche le refus d'un renommage vers un nom déjà pris", async () => {
    renameTrainingGroup.mockRejectedValue(new ApiError(422, "Un groupe porte déjà ce nom."));
    afficher();
    const dialog = await ouvrirLeGroupe();

    const nom = within(dialog).getByLabelText("Nom");
    await userEvent.clear(nom);
    await userEvent.type(nom, "Minimes");
    await userEvent.click(within(dialog).getByRole("button", { name: "Renommer" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Un groupe porte déjà ce nom."));
  });

  it("liste les membres, signale une adhésion terminée et ajoute un jeune", async () => {
    addTrainingGroupMember.mockResolvedValue(GROUPE);
    afficher();
    const dialog = await ouvrirLeGroupe();

    expect(await within(dialog).findByText("Alix Martin")).toBeInTheDocument();
    expect(within(dialog).getByText("Adhésion terminée, plus inscrit d'office")).toBeInTheDocument();
    expect(dialog).toHaveClass("max-h-[85dvh]", "overflow-y-auto");
    await userEvent.selectOptions(within(dialog).getByLabelText("Ajouter un jeune"), "3");

    await waitFor(() => expect(addTrainingGroupMember).toHaveBeenCalledWith(7, 3));
  });

  it("retire un membre", async () => {
    removeTrainingGroupMember.mockResolvedValue(GROUPE);
    afficher();
    const dialog = await ouvrirLeGroupe();

    await userEvent.click(await within(dialog).findByRole("button", { name: "Retirer Alix Martin" }));

    await waitFor(() => expect(removeTrainingGroupMember).toHaveBeenCalledWith(7, 1));
  });

  it("supprime un groupe après confirmation", async () => {
    deleteTrainingGroup.mockResolvedValue(null);
    afficher();
    const dialog = await ouvrirLeGroupe();

    await userEvent.click(within(dialog).getByRole("button", { name: "Supprimer le groupe" }));
    const confirmation = await screen.findByRole("dialog", {
      name: "Supprimer le groupe « Benjamins mercredi » ?",
    });
    await userEvent.click(within(confirmation).getByRole("button", { name: "Supprimer le groupe" }));

    await waitFor(() => expect(deleteTrainingGroup).toHaveBeenCalledWith(7));
  });

  it("reste en lecture seule sans jeunes:write", async () => {
    getSession.mockResolvedValue({ ...AVEC_ECRITURE, permissions: ["jeunes:read"] });
    afficher();
    const dialog = await ouvrirLeGroupe();

    expect(await within(dialog).findByText("Alix Martin")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nom du groupe")).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /supprimer|retirer|renommer/i })).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Ajouter un jeune")).not.toBeInTheDocument();
  });
});
