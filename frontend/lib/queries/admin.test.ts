import { QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createElement, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

const {
  updateAthlete,
  reassignParticipation,
  updateCourse,
  deleteCourse,
  listPermissions,
  listRoles,
  createRole,
  updateRole,
  deleteRole,
} = vi.hoisted(() => ({
  updateAthlete: vi.fn(),
  reassignParticipation: vi.fn(),
  updateCourse: vi.fn(),
  deleteCourse: vi.fn(),
  listPermissions: vi.fn(),
  listRoles: vi.fn(),
  createRole: vi.fn(),
  updateRole: vi.fn(),
  deleteRole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      updateAthlete,
      reassignParticipation,
      updateCourse,
      deleteCourse,
      listPermissions,
      listRoles,
      createRole,
      updateRole,
      deleteRole,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import {
  useUpdateAthlete,
  useUpdateCourse,
  useDeleteCourse,
  useReassignParticipation,
  useAdminPermissions,
  useRoles,
  useCreateRole,
  useUpdateRole,
  useDeleteRole,
} from "./admin";

/**
 * Les quatre gestes périment le cache des résultats d'une épreuve.
 *
 * C'est celui que lit `CourseParticipationsDialog`, et il est servi par
 * `apiClient.getCourse` — donc aucune des clés « évidentes » d'un geste ne le
 * touche. Sans invalidation, corriger un coureur laisse son ancien nom affiché
 * dans la liste d'où l'on vient de le corriger.
 */
let client: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client }, children);
}

describe("invalidations des gestes d'administration", () => {
  beforeEach(() => {
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    updateAthlete.mockResolvedValue({});
    reassignParticipation.mockResolvedValue({});
    updateCourse.mockResolvedValue({});
    deleteCourse.mockResolvedValue(undefined);
  });

  const gestes = [
    {
      nom: "corriger un coureur",
      hook: useUpdateAthlete,
      declencher: (mutate: (v: never) => void) =>
        mutate({ id: 1, champs: { nom: "Dupont" } } as never),
    },
    {
      nom: "rattacher un résultat",
      hook: useReassignParticipation,
      declencher: (mutate: (v: never) => void) =>
        mutate({ participationId: 7, athleteId: 2 } as never),
    },
    {
      nom: "corriger une épreuve",
      hook: useUpdateCourse,
      declencher: (mutate: (v: never) => void) =>
        mutate({ id: 12, champs: { name: "X" } } as never),
    },
    {
      nom: "supprimer une épreuve",
      hook: useDeleteCourse,
      declencher: (mutate: (v: never) => void) => mutate(12 as never),
    },
  ];

  it.each(gestes)("$nom périme le détail admin d'une épreuve", async ({ hook, declencher }) => {
    const invalider = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => hook(), { wrapper });

    declencher(result.current.mutate as (v: never) => void);

    await waitFor(() =>
      expect(invalider).toHaveBeenCalledWith({ queryKey: ["admin-course-detail"] }),
    );
  });
});

describe("lecture de la composition des rôles (#240)", () => {
  beforeEach(() => {
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    listPermissions.mockReset();
    listRoles.mockReset();
  });

  it("sert l'inventaire des pouvoirs sous sa propre clé", async () => {
    const inventaire = [{ feature: "Rôles et accès", permissions: [] }];
    listPermissions.mockResolvedValue(inventaire);

    const { result } = renderHook(() => useAdminPermissions(), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual(inventaire));
    expect(listPermissions).toHaveBeenCalled();
    expect(client.getQueryData(["admin-permissions"])).toEqual(inventaire);
  });

  it("sert la liste des rôles sous sa propre clé", async () => {
    const roles = [{ id: 1, slug: "admin", name: "Administrateur" }];
    listRoles.mockResolvedValue(roles);

    const { result } = renderHook(() => useRoles(), { wrapper });

    await waitFor(() => expect(result.current.data).toEqual(roles));
    expect(client.getQueryData(["roles"])).toEqual(roles);
  });

  /**
   * **Un 403 remonte, il n'est pas avalé en liste vide.**
   *
   * C'est le défaut déjà fermé deux fois — sur `PendingProvidersTable` puis sur
   * `AllowedEmailsTable`. Ici l'écran conclurait « aucun rôle n'existe » d'un
   * simple manque de droit, ce qui est la lecture la plus alarmante possible.
   */
  it.each([
    { nom: "l'inventaire", hook: useAdminPermissions, appel: listPermissions },
    { nom: "les rôles", hook: useRoles, appel: listRoles },
  ])("laisse un 403 sur $nom remonter à l'appelant", async ({ hook, appel }) => {
    appel.mockRejectedValue(new ApiError(403, "Pouvoir insuffisant."));

    const { result } = renderHook(() => hook(), { wrapper });

    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect((result.current.error as ApiError).status).toBe(403);
    expect(result.current.data).toBeUndefined();
  });

  /**
   * **Le `retry: false` doit être celui du hook, pas celui du client de test.**
   *
   * Les autres cas montent un `QueryClient` qui ne réessaie déjà pas, ce qui
   * masquerait sa disparition du hook. En production le défaut est de trois
   * tentatives — et sur un 403, insister ne change pas la réponse : cela ne fait
   * que retarder l'affichage du refus. Ce cas monte donc un client qui réessaie.
   */
  it.each([
    { nom: "l'inventaire", hook: useAdminPermissions, appel: listPermissions },
    { nom: "les rôles", hook: useRoles, appel: listRoles },
  ])("n'insiste pas sur un refus de $nom, même sous un client qui réessaie", async ({
    hook,
    appel,
  }) => {
    client = new QueryClient({ defaultOptions: { queries: { retry: 3, retryDelay: 0 } } });
    appel.mockRejectedValue(new ApiError(403, "Pouvoir insuffisant."));

    const { result } = renderHook(() => hook(), { wrapper });

    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiError));
    expect(appel).toHaveBeenCalledTimes(1);
  });
});

/**
 * Les trois gestes périment **aussi** la session.
 *
 * Recomposer un rôle qu'on porte soi-même est le cas nominal, pas un cas
 * limite : c'est même le seul rôle qu'un administrateur ait toujours sous la
 * main. Sans cette invalidation, `session.permissions` reste sur l'ancien état
 * et la grille continue de figer des cases que l'on porte désormais.
 */
describe("écriture de la composition des rôles (#240)", () => {
  const gestes = [
    {
      nom: "créer un rôle",
      hook: useCreateRole,
      appel: createRole,
      declencher: (mutate: (v: never) => void) =>
        mutate({ slug: "benevole", name: "Bénévole" } as never),
      attendu: [{ slug: "benevole", name: "Bénévole" }],
    },
    {
      nom: "recomposer un rôle",
      hook: useUpdateRole,
      appel: updateRole,
      declencher: (mutate: (v: never) => void) =>
        mutate({ id: 2, champs: { permissions: ["roles:read"] } } as never),
      attendu: [2, { permissions: ["roles:read"] }],
    },
    {
      nom: "supprimer un rôle",
      hook: useDeleteRole,
      appel: deleteRole,
      declencher: (mutate: (v: never) => void) => mutate(3 as never),
      attendu: [3],
    },
  ];

  beforeEach(() => {
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    createRole.mockResolvedValue({});
    updateRole.mockResolvedValue({});
    deleteRole.mockResolvedValue(undefined);
  });

  it.each(gestes)("$nom appelle le client et périme rôles et session", async ({
    hook,
    appel,
    declencher,
    attendu,
  }) => {
    const invalider = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => hook(), { wrapper });

    declencher(result.current.mutate as (v: never) => void);

    await waitFor(() => expect(appel).toHaveBeenCalledWith(...attendu));
    expect(invalider).toHaveBeenCalledWith({ queryKey: ["roles"] });
    expect(invalider).toHaveBeenCalledWith({ queryKey: ["session"] });
  });
});
