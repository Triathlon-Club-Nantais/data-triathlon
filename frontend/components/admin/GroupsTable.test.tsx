import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { ApiError } from "@/lib/api/client";
import { DangerConfirmProvider } from "./DangerConfirm";
import { confirmerDansLeDialog } from "./__tests__/dangerConfirm";
import type { Group, GroupDetail, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { listGroups, getGroup, createGroup, deleteGroup, listAdminUsers, getSession } =
  vi.hoisted(() => ({
    listGroups: vi.fn(),
    getGroup: vi.fn(),
    createGroup: vi.fn(),
    deleteGroup: vi.fn(),
    listAdminUsers: vi.fn(),
    getSession: vi.fn(),
  }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listGroups, getGroup, createGroup, deleteGroup, listAdminUsers, getSession },
  };
});

import { GroupsTable } from "./GroupsTable";

const CODIR: Group = {
  id: 3,
  organisation_id: 1,
  slug: "codir",
  name: "Codir",
  description: "Comité de direction du club.",
  member_count: 2,
  created_at: "2026-07-01T09:00:00Z",
};

const DETAIL_CODIR: GroupDetail = { ...CODIR, members: [] };

/** Une session qui peut tout faire sur les groupes. */
const MOI: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["groups:read", "groups:write", "groups:assign", "users:read"],
  roles: [],
  groups: [],
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DangerConfirmProvider>
        <GroupsTable />
      </DangerConfirmProvider>
    </QueryClientProvider>,
  );
}

const VIDE: Group = { ...CODIR, id: 4, slug: "officiels", name: "Officiels", member_count: 0 };

describe("GroupsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(MOI);
    listAdminUsers.mockResolvedValue([]);
    getGroup.mockResolvedValue(DETAIL_CODIR);
  });

  it("liste les groupes avec leur nombre de membres", async () => {
    listGroups.mockResolvedValue([CODIR]);

    afficher();

    expect(await screen.findByText("Codir")).toBeInTheDocument();
    expect(screen.getByText(/comité de direction/i)).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("dit « aucun groupe » sur une liste vide", async () => {
    listGroups.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun groupe/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403, et non « aucun groupe »", async () => {
    listGroups.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
    // La description aussi : elle seule ancre le `REFUS` de cet écran, le titre
    // étant commun aux quatre écrans qui partagent `messageDeRefus`.
    expect(
      screen.getByText(/ne permet pas de consulter les groupes d'appartenance/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/aucun groupe/i)).not.toBeInTheDocument();
  });

  it("distingue la session expirée du refus de droit", async () => {
    listGroups.mockRejectedValue(new ApiError(401, "Non connecté"));

    afficher();

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
    expect(screen.queryByText(/accès refusé/i)).not.toBeInTheDocument();
  });

  it("crée un groupe à partir de son nom et de son identifiant", async () => {
    listGroups.mockResolvedValue([]);
    createGroup.mockResolvedValue(DETAIL_CODIR);

    afficher();
    await screen.findByText(/aucun groupe/i);
    await userEvent.type(screen.getByLabelText(/^nom/i), "Codir");
    await userEvent.type(screen.getByLabelText(/identifiant/i), "codir");
    await userEvent.click(screen.getByRole("button", { name: /créer le groupe/i }));

    await waitFor(() =>
      expect(createGroup).toHaveBeenCalledWith({
        slug: "codir",
        name: "Codir",
        description: "",
      }),
    );
  });

  it("annonce avant le clic, en texte visible, qu'un groupe peuplé ne peut pas être supprimé", async () => {
    // Texte visible et permanent, pas une infobulle : atteignable au tactile,
    // sans survol ni focus (#499, revue de fin de branche).
    listGroups.mockResolvedValue([CODIR]); // member_count: 2
    afficher();
    const bouton = await screen.findByRole("button", { name: "Supprimer le groupe Codir" });
    expect(bouton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("2 membres — videz-le d'abord")).toBeInTheDocument();
  });

  it("exige une confirmation nominative avant de supprimer un groupe vide", async () => {
    listGroups.mockResolvedValue([VIDE]);
    afficher();
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer le groupe Officiels" }));
    expect(screen.getByText("Supprimer « Officiels » ?")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));
    expect(deleteGroup).not.toHaveBeenCalled();
  });

  it("supprime le groupe vide une fois la confirmation donnée", async () => {
    listGroups.mockResolvedValue([VIDE]);
    deleteGroup.mockResolvedValue(undefined);
    afficher();
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer le groupe Officiels" }));
    await confirmerDansLeDialog("Supprimer définitivement");
    await waitFor(() => expect(deleteGroup).toHaveBeenCalledWith(VIDE.id));
  });

  it("affiche tel quel le refus serveur de supprimer un groupe", async () => {
    // 409 : la demande est bien formée et l'appelant en a le droit, c'est le
    // résultat qui est interdit — ici une composition changée entre
    // l'affichage et la confirmation. Le message vient du serveur, déjà en
    // français.
    listGroups.mockResolvedValue([VIDE]);
    deleteGroup.mockRejectedValue(new ApiError(409, "Ce groupe compte encore 1 membre."));

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer le groupe Officiels" }));
    await confirmerDansLeDialog("Supprimer définitivement");

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Ce groupe compte encore 1 membre."),
    );
  });

  it("n'offre ni création ni suppression sans `groups:write`", async () => {
    // Consulter les groupes est `groups:read` ; les proposer ferait miroiter un
    // geste que l'API rendrait en 403.
    getSession.mockResolvedValue({ ...MOI, permissions: ["groups:read"] });
    listGroups.mockResolvedValue([CODIR]);

    afficher();
    await screen.findByText("Codir");

    expect(screen.queryByRole("button", { name: /créer le groupe/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /supprimer le groupe/i }),
    ).not.toBeInTheDocument();
  });

  it("ouvre la composition d'un groupe", async () => {
    listGroups.mockResolvedValue([CODIR]);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: "Codir" }));

    await waitFor(() => expect(getGroup).toHaveBeenCalledWith(CODIR.id));
  });
});
