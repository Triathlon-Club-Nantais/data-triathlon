import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminUser, Group, GroupDetail, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const {
  getGroup,
  updateGroup,
  addGroupMember,
  removeGroupMember,
  listAdminUsers,
  getSession,
} = vi.hoisted(() => ({
  getGroup: vi.fn(),
  updateGroup: vi.fn(),
  addGroupMember: vi.fn(),
  removeGroupMember: vi.fn(),
  listAdminUsers: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      getGroup,
      updateGroup,
      addGroupMember,
      removeGroupMember,
      listAdminUsers,
      getSession,
    },
  };
});

import { GroupDetailDialog } from "./GroupDetailDialog";

const CODIR: Group = {
  id: 3,
  organisation_id: 1,
  slug: "codir",
  name: "Codir",
  description: "Comité de direction du club.",
  member_count: 2,
  created_at: "2026-07-01T09:00:00Z",
};

const DETAIL: GroupDetail = {
  ...CODIR,
  members: [
    {
      user_id: 7,
      email: "camille@exemple.fr",
      display_name: "Camille Durand",
      is_active: true,
      joined_at: "2026-07-02T10:00:00Z",
    },
    {
      user_id: 8,
      email: "dominique@exemple.fr",
      display_name: "Dominique Martin",
      is_active: false,
      joined_at: "2026-07-03T10:00:00Z",
    },
  ],
};

const CAMILLE: AdminUser = {
  id: 7,
  email: "camille@exemple.fr",
  display_name: "Camille Durand",
  is_active: true,
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
};

const ALIX: AdminUser = {
  id: 9,
  email: "alix@exemple.fr",
  display_name: "Alix Petit",
  is_active: true,
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
};

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
      <GroupDetailDialog group={CODIR} open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

describe("GroupDetailDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(MOI);
    getGroup.mockResolvedValue(DETAIL);
    listAdminUsers.mockResolvedValue([CAMILLE, ALIX]);
  });

  it("affiche les membres du groupe", async () => {
    afficher();

    expect(await screen.findByText("Camille Durand")).toBeInTheDocument();
    expect(screen.getByText("camille@exemple.fr")).toBeInTheDocument();
  });

  it("distingue un membre désactivé, qui reste membre", async () => {
    // Un compte désactivé (#170) ne peut plus ouvrir de session, mais son
    // appartenance survit : l'écran mentirait en le montrant comme les autres,
    // et mentirait tout autant en le cachant.
    afficher();

    await screen.findByText("Dominique Martin");
    expect(screen.getByText(/désactivé/i)).toBeInTheDocument();
  });

  it("dit « aucun membre » sur un groupe vide", async () => {
    getGroup.mockResolvedValue({ ...DETAIL, members: [] });

    afficher();

    expect(await screen.findByText(/aucun membre/i)).toBeInTheDocument();
  });

  it("ajoute un membre choisi parmi les utilisateurs", async () => {
    afficher();
    await screen.findByText("Camille Durand");
    await userEvent.selectOptions(
      screen.getByLabelText(/ajouter un membre/i),
      String(ALIX.id),
    );

    await waitFor(() => expect(addGroupMember).toHaveBeenCalledWith(CODIR.id, ALIX.id));
  });

  it("ne propose pas quelqu'un qui est déjà membre", async () => {
    afficher();
    const selecteur = await screen.findByLabelText(/ajouter un membre/i);

    expect(within(selecteur).getByRole("option", { name: /alix petit/i })).toBeInTheDocument();
    expect(
      within(selecteur).queryByRole("option", { name: /camille durand/i }),
    ).not.toBeInTheDocument();
  });

  it("retire un membre sans confirmation — le geste ne coupe aucune session", async () => {
    // À l'inverse du retrait d'une adresse autorisée (#170), qui ferme les
    // sessions ouvertes. Les deux gestes ne doivent pas se ressembler.
    const confirmation = vi.spyOn(window, "confirm").mockReturnValue(true);
    afficher();
    await screen.findByText("Camille Durand");
    await userEvent.click(
      screen.getByRole("button", { name: /retirer camille durand du groupe/i }),
    );

    await waitFor(() =>
      expect(removeGroupMember).toHaveBeenCalledWith(CODIR.id, CAMILLE.id),
    );
    expect(confirmation).not.toHaveBeenCalled();
    confirmation.mockRestore();
  });

  it("n'offre ni ajout ni retrait sans `groups:assign`", async () => {
    getSession.mockResolvedValue({ ...MOI, permissions: ["groups:read"] });

    afficher();
    await screen.findByText("Camille Durand");

    expect(screen.queryByLabelText(/ajouter un membre/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /retirer camille/i })).not.toBeInTheDocument();
  });

  it("renomme et redécrit le groupe", async () => {
    updateGroup.mockResolvedValue(DETAIL);

    afficher();
    const nom = await screen.findByLabelText(/^nom/i);
    await userEvent.clear(nom);
    await userEvent.type(nom, "Comité directeur");
    await userEvent.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() =>
      expect(updateGroup).toHaveBeenCalledWith(CODIR.id, {
        name: "Comité directeur",
        description: DETAIL.description,
      }),
    );
  });

  it("intitule la modale d'après le détail, pas d'après la ligne cliquée", async () => {
    // Le nom de la prop est un instantané pris au clic. Après un renommage, le
    // détail est réinterrogé et porte le nouveau nom : titrer avec la prop
    // laisserait l'ancien nom au bandeau du geste qu'on vient de confirmer.
    getGroup.mockResolvedValue({ ...DETAIL, name: "Comité directeur" });

    afficher();

    expect(await screen.findByText("Comité directeur")).toBeInTheDocument();
  });

  it("périme sa propre session en modifiant une appartenance", async () => {
    // `GET /auth/me` rend `groups`, et `UserMenu` l'affiche : s'ajouter au Codir
    // sans réinterroger la session laisse son propre menu mentir sur soi.
    addGroupMember.mockResolvedValue(DETAIL);

    afficher();
    await screen.findByText("Camille Durand");
    await waitFor(() => expect(getSession).toHaveBeenCalledTimes(1));
    await userEvent.selectOptions(
      screen.getByLabelText(/ajouter un membre/i),
      String(ALIX.id),
    );

    await waitFor(() => expect(getSession).toHaveBeenCalledTimes(2));
  });

  it("nomme par son adresse un compte sans nom affiché", async () => {
    // `display_name` vaut `""` par défaut en base et chez deux fournisseurs
    // d'identité : une option vide serait impossible à choisir sciemment.
    const SANS_NOM = { ...ALIX, display_name: "" };
    listAdminUsers.mockResolvedValue([SANS_NOM]);
    getGroup.mockResolvedValue({
      ...DETAIL,
      members: [
        {
          user_id: 11,
          email: "anonyme@exemple.fr",
          display_name: "",
          is_active: true,
          joined_at: "2026-07-04T10:00:00Z",
        },
      ],
    });

    afficher();
    const selecteur = await screen.findByLabelText(/ajouter un membre/i);

    expect(within(selecteur).getByRole("option", { name: SANS_NOM.email })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Retirer anonyme@exemple.fr du groupe" }),
    ).toBeInTheDocument();
  });

  it("dit pourquoi le choix d'un membre est vide quand `users:read` manque", async () => {
    // Porter `groups:assign` sans `users:read` est le cas qui justifie le
    // `retry: false` de `useAdminUsers` : le sélecteur reste vide, et sans un
    // mot l'écran laisserait croire qu'il n'existe aucun utilisateur.
    listAdminUsers.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/pouvoir les consulter/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/ajouter un membre/i)).toBeDisabled();
  });

  it("n'offre pas de renommage sans `groups:write`", async () => {
    getSession.mockResolvedValue({ ...MOI, permissions: ["groups:read", "groups:assign"] });

    afficher();
    await screen.findByText("Camille Durand");

    expect(screen.queryByRole("button", { name: /enregistrer/i })).not.toBeInTheDocument();
  });
});
