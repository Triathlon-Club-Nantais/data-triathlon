import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { SessionUser } from "@/lib/types";

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession } };
});

import { AdminIndex } from "./AdminIndex";

const SESSION = (permissions: string[]): SessionUser =>
  ({
    id: 1,
    email: "benevole@exemple.fr",
    display_name: "Bénévole",
    roles: [],
    permissions,
  }) as unknown as SessionUser;

function afficher() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AdminIndex />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AdminIndex", () => {
  it("désambiguïse les écrans aux noms proches par leur phrase", async () => {
    // Le motif d'ADM-6 : « Groupes d'appartenance » et « Droits des rôles » ne
    // se distinguent pas par leur libellé pour un bénévole non formé.
    getSession.mockResolvedValue(SESSION(["groups:assign", "roles:write"]));
    afficher();

    expect(
      await screen.findByRole("link", { name: /Groupes d'appartenance/ }),
    ).toHaveAttribute("href", "/admin/groupes");
    expect(screen.getByText(/Un groupe n'accorde aucun droit/)).toBeInTheDocument();
    expect(screen.getByText(/Un rôle porte des pouvoirs/)).toBeInTheDocument();
  });

  it("n'annonce que les écrans que la session peut ouvrir", async () => {
    getSession.mockResolvedValue(SESSION(["feedback:read"]));
    afficher();

    await screen.findByRole("link", { name: /Retours utilisateurs/ });
    expect(screen.queryByRole("link", { name: /Épreuves/ })).toBeNull();
    expect(screen.queryByText("Gestion des utilisateurs")).toBeNull();
  });

  it("dit qu'aucun écran n'est ouvert plutôt que de rester muet", async () => {
    getSession.mockResolvedValue(SESSION([]));
    afficher();

    expect(await screen.findByText(/Aucun écran d'administration/)).toBeInTheDocument();
  });

  it("ne confond pas une session illisible avec une absence de pouvoirs", async () => {
    getSession.mockRejectedValue(new ApiError(503, "Backend injoignable."));
    afficher();

    // La phrase est fixe et française : le repli d'`ApiError` est `statusText`,
    // donc anglais, et le réveil à froid du backend n'est même pas une
    // `ApiError`. Le message du serveur ne sort donc jamais ici.
    expect(
      await screen.findByText(/Vos pouvoirs n'ont pas pu être lus/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/injoignable/i)).toBeNull();
    expect(screen.queryByText(/Aucun écran d'administration/)).toBeNull();
  });
});
