import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminUser, Role, SessionUser } from "@/lib/types";

const { listAdminUsers, listRoles, grantRole, revokeRole, getSession } = vi.hoisted(
  () => ({
    listAdminUsers: vi.fn(),
    listRoles: vi.fn(),
    grantRole: vi.fn(),
    revokeRole: vi.fn(),
    getSession: vi.fn(),
  }),
);

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listAdminUsers, listRoles, grantRole, revokeRole, getSession },
  };
});

import { UserRolesTable } from "./UserRolesTable";

const ADMINISTRATEUR: Role = {
  id: 1,
  organisation_id: 1,
  slug: "admin",
  name: "Administrateur",
  description: "Peut tout faire.",
  is_system: true,
  is_superuser: true,
  permissions: ["roles:assign"],
  stale_permissions: [],
  holders: 1,
};

const BENEVOLE: Role = {
  id: 2,
  organisation_id: 1,
  slug: "benevole",
  name: "Bénévole",
  description: "",
  is_system: false,
  is_superuser: false,
  permissions: [],
  stale_permissions: [],
  holders: 0,
};

/** Un rôle qui porte un pouvoir que la session courante n'a pas. */
const TRESORIER: Role = {
  id: 3,
  organisation_id: 1,
  slug: "tresorier",
  name: "Trésorier",
  description: "",
  is_system: false,
  is_superuser: false,
  permissions: ["roles:write"],
  stale_permissions: [],
  holders: 0,
};

/** La session qui pilote l'écran : elle porte de quoi le voir et attribuer. */
const MOI: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["users:read", "roles:read", "roles:assign"],
  roles: [],
};

const CAMILLE: AdminUser = {
  id: 7,
  email: "camille@exemple.fr",
  display_name: "Camille Durand",
  is_active: true,
  roles: [ADMINISTRATEUR],
  created_at: "2026-08-01T14:54:28Z",
};

const DOMINIQUE: AdminUser = {
  id: 8,
  email: "dominique@exemple.fr",
  display_name: "Dominique Martin",
  is_active: false,
  roles: [],
  created_at: "2026-08-02T09:00:00Z",
};

function afficher() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <UserRolesTable />
    </QueryClientProvider>,
  );
}

describe("UserRolesTable", () => {
  beforeEach(() => {
    listAdminUsers.mockReset();
    listRoles.mockReset();
    grantRole.mockReset();
    revokeRole.mockReset();
    getSession.mockReset();
    listRoles.mockResolvedValue([ADMINISTRATEUR, BENEVOLE]);
    getSession.mockResolvedValue(MOI);
  });

  it("affiche les utilisateurs et les rôles qu'ils portent", async () => {
    listAdminUsers.mockResolvedValue([CAMILLE]);

    afficher();

    expect(await screen.findByText(CAMILLE.email)).toBeInTheDocument();
    expect(screen.getByText(/camille durand/i)).toBeInTheDocument();
    expect(screen.getByText(ADMINISTRATEUR.name)).toBeInTheDocument();
  });

  it("distingue un compte désactivé", async () => {
    // Un compte désactivé est l'effet d'un retrait de la liste d'autorisation
    // (#170) : il reste en base, ses rôles restent visibles, mais il ne peut
    // plus ouvrir de session — l'écran mentirait en le montrant comme les
    // autres.
    listAdminUsers.mockResolvedValue([CAMILLE, DOMINIQUE]);

    afficher();

    await screen.findByText(DOMINIQUE.email);
    expect(screen.getByText(/désactivé/i)).toBeInTheDocument();
  });

  it("dit « aucun utilisateur » sur une liste vide", async () => {
    listAdminUsers.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun utilisateur/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403, et non « aucun utilisateur »", async () => {
    listAdminUsers.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun utilisateur/i)).not.toBeInTheDocument();
  });

  it("distingue la session expirée du refus de droit", async () => {
    listAdminUsers.mockRejectedValue(new ApiError(401, "Non connecté"));

    afficher();

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
    expect(screen.queryByText(/accès refusé/i)).not.toBeInTheDocument();
  });

  it("attribue un rôle que l'utilisateur ne porte pas encore", async () => {
    listAdminUsers.mockResolvedValue([DOMINIQUE]);
    grantRole.mockResolvedValue({ ...DOMINIQUE, roles: [BENEVOLE] });

    afficher();
    await screen.findByText(DOMINIQUE.email);
    await userEvent.selectOptions(
      await screen.findByLabelText(/attribuer un rôle à dominique martin/i),
      String(BENEVOLE.id),
    );

    await waitFor(() =>
      expect(grantRole).toHaveBeenCalledWith(DOMINIQUE.id, BENEVOLE.id),
    );
  });

  it("ne propose pas un rôle déjà porté", async () => {
    listAdminUsers.mockResolvedValue([CAMILLE]);

    afficher();
    const selecteur = await screen.findByLabelText(
      /attribuer un rôle à camille durand/i,
    );

    expect(
      screen.queryByRole("option", { name: ADMINISTRATEUR.name }),
    ).not.toBeInTheDocument();
    expect(
      within(selecteur).getByRole("option", { name: BENEVOLE.name }),
    ).toBeInTheDocument();
  });

  it("propose sans le rendre choisissable un rôle qu'on ne pourrait pas accorder", async () => {
    // Non-amplification (FR-011) : nul n'accorde un pouvoir qu'il ne porte pas.
    // Le service la tient — l'écran ne doit pas laisser croire l'inverse en
    // proposant un rôle qui rendrait 403. Il le montre plutôt que de le cacher,
    // pour que « pourquoi ce rôle manque-t-il ? » ne se pose pas.
    listRoles.mockResolvedValue([BENEVOLE, TRESORIER]);
    listAdminUsers.mockResolvedValue([DOMINIQUE]);

    afficher();
    const selecteur = await screen.findByLabelText(
      /attribuer un rôle à dominique martin/i,
    );

    expect(
      within(selecteur).getByRole("option", { name: /trésorier/i }),
    ).toBeDisabled();
    expect(
      within(selecteur).getByRole("option", { name: BENEVOLE.name }),
    ).toBeEnabled();
  });

  it("ne laisse pas distribuer le rôle administrateur à qui ne l'est pas", async () => {
    // Le rôle `admin` semé ne porte **aucun** code : il atteint tout par
    // `is_superuser`. La comparaison de codes le laisse donc passer, et c'est
    // le service qui refuse en 403 (FR-010). Sans cette ligne, l'écran
    // proposerait le rôle le plus lourd de l'application comme un autre.
    listAdminUsers.mockResolvedValue([DOMINIQUE]);

    afficher();
    const selecteur = await screen.findByLabelText(
      /attribuer un rôle à dominique martin/i,
    );

    expect(
      within(selecteur).getByRole("option", { name: ADMINISTRATEUR.name }),
    ).toBeDisabled();
  });

  it("le laisse distribuer à un superutilisateur", async () => {
    // Reconnu par recoupement : la session nomme les rôles qu'elle porte,
    // l'inventaire dit lesquels sont superutilisateurs. Les deux listes sont
    // déjà chargées par l'écran.
    getSession.mockResolvedValue({ ...MOI, roles: [ADMINISTRATEUR] });
    listAdminUsers.mockResolvedValue([DOMINIQUE]);

    afficher();
    const selecteur = await screen.findByLabelText(
      /attribuer un rôle à dominique martin/i,
    );

    expect(
      within(selecteur).getByRole("option", { name: ADMINISTRATEUR.name }),
    ).toBeEnabled();
  });

  it("retire un rôle porté", async () => {
    listAdminUsers.mockResolvedValue([CAMILLE]);
    revokeRole.mockResolvedValue(null);

    afficher();
    await screen.findByText(CAMILLE.email);
    await userEvent.click(
      screen.getByRole("button", { name: /retirer le rôle administrateur/i }),
    );

    await waitFor(() =>
      expect(revokeRole).toHaveBeenCalledWith(CAMILLE.id, ADMINISTRATEUR.id),
    );
  });

  it("affiche le refus du dernier administrateur tel que rendu par l'API", async () => {
    // 409 : l'appelant est bien administrateur et sa requête bien formée, c'est
    // le résultat qui est interdit. Le message vient du serveur — le front le
    // rend verbatim et laisse la liste inchangée.
    listAdminUsers.mockResolvedValue([CAMILLE]);
    revokeRole.mockRejectedValue(
      new ApiError(409, "Cette organisation perdrait son dernier administrateur."),
    );

    afficher();
    await screen.findByText(CAMILLE.email);
    await userEvent.click(
      screen.getByRole("button", { name: /retirer le rôle administrateur/i }),
    );

    await waitFor(() => expect(revokeRole).toHaveBeenCalled());
    expect(screen.getByText(ADMINISTRATEUR.name)).toBeInTheDocument();
  });
});
