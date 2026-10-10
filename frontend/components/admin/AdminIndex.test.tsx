import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { SessionUser } from "@/lib/types";

const { getSession, countFeedback, countIdentityReview } = vi.hoisted(() => ({
  getSession: vi.fn(),
  countFeedback: vi.fn(),
  countIdentityReview: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, countFeedback, countIdentityReview } };
});

import { AdminIndex } from "./AdminIndex";

const SESSION = (permissions: string[]): SessionUser =>
  ({
    id: 1,
    email: "benevole@exemple.fr",
    display_name: "Bénévole",
    roles: [],
    permissions,
    // Miroir du catalogue backend (#1109, #1297) : `pages:preview` consulte, les
    // pouvoirs de supervision (jeunes, validation des crédits) ne comptent pas.
    can_administer: permissions.some(
      (code) => !["pages:preview", "jeunes:read", "jeunes:write", "athletes:volunteer_validate"].includes(code),
    ),
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
  countFeedback.mockResolvedValue({ nouveau: 0 });
  countIdentityReview.mockResolvedValue({ total: 0 });
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

  it.each([
    ["sans pouvoir", []],
    ["ne portant que `pages:preview` (#1109)", ["pages:preview"]],
  ])("dit à une session %s qu'aucun écran n'est ouvert, comme la garde", async (_cas, pouvoirs) => {
    getSession.mockResolvedValue(SESSION(pouvoirs));
    afficher();

    expect(await screen.findByText(/vous êtes connecté/i)).toBeInTheDocument();
    expect(screen.getByText(/demandez un rôle à un administrateur du club/i)).toBeInTheDocument();
  });

  // Un pouvoir d'administration sans écran à lui (`courses:delete` sans
  // `courses:write`) : même texte et même sortie que la garde (revue UI/UX).
  it("rend le même état qu'une session sans pouvoir quand aucun écran n'est annoncé", async () => {
    getSession.mockResolvedValue(SESSION(["courses:delete"]));
    afficher();

    expect(await screen.findByText(/vous êtes connecté/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Retour au site" })).toHaveAttribute("href", "/dashboard");
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

describe("AdminIndex: work queues first (#1246)", () => {
  it("puts first the queues open to the session, with their count and link", async () => {
    countFeedback.mockResolvedValue({ nouveau: 3 });
    getSession.mockResolvedValue(SESSION(["feedback:read", "athletes:write", "admin_log:read"]));
    afficher();

    const files = await screen.findByRole("region", { name: "À traiter" });
    const retours = within(files).getByRole("link", { name: /Retours utilisateurs/ });
    expect(retours).toHaveAttribute("href", "/admin/retours-utilisateurs");
    expect(await within(retours).findByText("3 nouveaux retours utilisateurs")).toBeInTheDocument();
    expect(await within(files).findByText("Rien en attente")).toBeInTheDocument();
    expect(within(files).queryByRole("link", { name: /Journal/ })).toBeNull();
  });

  it("shows a discreet ellipsis while a counter loads", async () => {
    countFeedback.mockReturnValue(new Promise(() => {}));
    getSession.mockResolvedValue(SESSION(["feedback:read"]));
    afficher();

    const files = await screen.findByRole("region", { name: "À traiter" });
    const loading = within(files).getByText("…");
    expect(loading).toHaveAttribute("aria-hidden", "true");
    expect(within(files).queryByText("Rien en attente")).toBeNull();
  });

  it("files the other screens under their subsections, without repeating the queues", async () => {
    getSession.mockResolvedValue(SESSION(["feedback:read", "admin_log:read"]));
    afficher();

    expect(await screen.findByRole("heading", { name: "Conformité" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Journal d'administration/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Retours utilisateurs/ })).toHaveLength(1);
  });
});
