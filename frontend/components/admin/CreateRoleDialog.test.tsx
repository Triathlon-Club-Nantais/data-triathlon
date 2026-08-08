import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { PermissionGroup } from "@/lib/types";

const { createRole } = vi.hoisted(() => ({ createRole: vi.fn() }));
const { toastError, toastSuccess } = vi.hoisted(() => ({
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { createRole } };
});

import { CreateRoleDialog } from "./CreateRoleDialog";

const INVENTAIRE: PermissionGroup[] = [
  {
    feature: "Rôles et accès",
    permissions: [
      {
        code: "roles:read",
        label: "Consulter les rôles",
        description: "Voir la liste des rôles et leur composition.",
      },
    ],
  },
];

function afficher(
  props: { disabledCodes?: ReadonlySet<string>; raison?: string } = {},
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CreateRoleDialog inventaire={INVENTAIRE} open onOpenChange={() => {}} {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  createRole.mockReset();
  toastError.mockReset();
  toastSuccess.mockReset();
});

describe("CreateRoleDialog", () => {
  /**
   * Le slug est **fixé une fois pour toutes** : il traverse `grant-role --role`
   * et le semis, et `RoleUpdate` le refuse ensuite par `extra="forbid"`. Le
   * laisser se fabriquer en silence, c'est le découvrir quand il est trop tard
   * pour le corriger — d'où un champ visible, prérempli.
   */
  it("dérive l'identifiant du nom, sans accent ni espace", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText(/nom du rôle/i), "Bénévole du club");

    expect(screen.getByLabelText(/identifiant/i)).toHaveValue("benevole-du-club");
  });

  it("laisse corriger l'identifiant à la main, et cesse alors de le dériver", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText(/nom du rôle/i), "Bénévole");
    await userEvent.clear(screen.getByLabelText(/identifiant/i));
    await userEvent.type(screen.getByLabelText(/identifiant/i), "benevoles-2026");
    await userEvent.type(screen.getByLabelText(/nom du rôle/i), " du club");

    expect(screen.getByLabelText(/identifiant/i)).toHaveValue("benevoles-2026");
  });

  it("compose l'état initial avec la même grille que l'édition", async () => {
    createRole.mockResolvedValue({});
    afficher();

    await userEvent.type(screen.getByLabelText(/nom du rôle/i), "Bénévole");
    expect(screen.getByRole("group", { name: "Rôles et accès" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /Consulter les rôles/ }));
    await userEvent.click(screen.getByRole("button", { name: "Créer le rôle" }));

    expect(createRole).toHaveBeenCalledWith({
      slug: "benevole",
      name: "Bénévole",
      description: "",
      permissions: ["roles:read"],
    });
  });

  it("restitue le refus du serveur sans vider la saisie", async () => {
    createRole.mockRejectedValue(
      new ApiError(409, "Un rôle porte déjà cet identifiant dans cette portée."),
    );
    afficher();

    await userEvent.type(screen.getByLabelText(/nom du rôle/i), "Bénévole");
    await userEvent.click(screen.getByRole("button", { name: "Créer le rôle" }));

    await vi.waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Un rôle porte déjà cet identifiant dans cette portée.",
      ),
    );
    expect(screen.getByLabelText(/nom du rôle/i)).toHaveValue("Bénévole");
    expect(screen.getByLabelText(/identifiant/i)).toHaveValue("benevole");
  });

  it("n'envoie rien tant que le nom est vide", async () => {
    afficher();

    expect(screen.getByRole("button", { name: "Créer le rôle" })).toBeDisabled();
  });

  /**
   * **La non-amplification vaut aussi à la création — et plus durement.**
   *
   * `authorization.create_role` passe `assert_may_grant` l'**ensemble complet**
   * des codes, là où `update_role` ne lui passe que la différence symétrique.
   * Une case laissée cochable ici, c'est un 403 garanti après que la personne a
   * composé tout son rôle.
   */
  it("fige les pouvoirs que la session ne porte pas, comme la grille d'édition", async () => {
    afficher({
      disabledCodes: new Set(["roles:read"]),
      raison: "Vous ne portez pas ce pouvoir : vous ne pouvez pas l'accorder.",
    });

    expect(screen.getByRole("checkbox", { name: /Consulter les rôles/ })).toBeDisabled();
    expect(screen.getByText(/vous ne portez pas ce pouvoir/i)).toBeInTheDocument();
  });

  /**
   * `RoleCreate.slug` vaut `Field(pattern=r"^[a-z][a-z0-9-]*$")`. Sans garde
   * locale, un identifiant corrigé à la main part au serveur et revient en
   * `String should match pattern '^[a-z][a-z0-9-]*$'` — du Pydantic anglais
   * dans une interface française.
   */
  it("retient un identifiant que le serveur refuserait, et dit ce qu'il attend", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText(/nom du rôle/i), "Bénévole");
    await userEvent.clear(screen.getByLabelText(/identifiant/i));
    await userEvent.type(screen.getByLabelText(/identifiant/i), "Bénévole 2026");

    expect(screen.getByRole("button", { name: "Créer le rôle" })).toBeDisabled();
    expect(screen.getByText(/lettre minuscule/i)).toBeInTheDocument();
    expect(createRole).not.toHaveBeenCalled();
  });

  /** Un nom sans lettre ne donne aucun identifiant : le dire, plutôt que d'inerter le bouton. */
  it("explique le bouton inerte quand le nom ne donne aucun identifiant", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText(/nom du rôle/i), "42");

    expect(screen.getByLabelText(/identifiant/i)).toHaveValue("");
    expect(screen.getByRole("button", { name: "Créer le rôle" })).toBeDisabled();
    expect(screen.getByText(/lettre minuscule/i)).toBeInTheDocument();
  });

  /**
   * Conserver la saisie après un **refus** est voulu (l'identifiant est à
   * corriger, pas à ressaisir) ; la conserver après un renoncement explicite ne
   * l'est pas — la modale rouvrirait sur le brouillon d'un rôle abandonné.
   */
  it("vide la saisie quand on renonce, et seulement alors", async () => {
    afficher();

    await userEvent.type(screen.getByLabelText(/nom du rôle/i), "Bénévole");
    await userEvent.click(screen.getByRole("button", { name: "Renoncer" }));

    expect(screen.getByLabelText(/nom du rôle/i)).toHaveValue("");
    expect(screen.getByLabelText(/identifiant/i)).toHaveValue("");
  });
});
