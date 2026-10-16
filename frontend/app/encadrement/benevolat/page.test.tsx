import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("@/lib/api/server", () => ({ apiServer: { getSession } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }), unstable_rethrow: () => {} }));
vi.mock("@/components/benevolat/AdminVolunteerActionsTable", () => ({
  AdminVolunteerActionsTable: () => <div data-testid="file-benevolat" />,
}));

import AdminBenevolatPage from "./page";

const session = (permissions: string[]) => ({
  id: 1,
  email: "admin@exemple.fr",
  display_name: "Admin",
  created_at: "2026-09-01T00:00:00Z",
  permissions,
  roles: [],
  groups: [],
  can_administer: true,
});

beforeEach(() => vi.clearAllMocks());

// #879 : l'admin du bénévolat suit ses écrans publics derrière `pages:preview`.
describe("AdminBenevolatPage", () => {
  it("rend le refus à un validateur sans pages:preview", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_validate"]));

    render(await AdminBenevolatPage());

    expect(screen.queryByTestId("file-benevolat")).not.toBeInTheDocument();
    expect(screen.getByText("Vous n'avez pas la permission nécessaire")).toBeInTheDocument();
  });

  it("rend la file à qui porte les deux pouvoirs", async () => {
    getSession.mockResolvedValue(session(["athletes:volunteer_validate", "pages:preview"]));

    render(await AdminBenevolatPage());

    expect(screen.getByTestId("file-benevolat")).toBeInTheDocument();
  });

  it("rend l'écran d'indisponibilité si la session ne se lit pas, sans planter", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    getSession.mockRejectedValue(new TypeError("fetch failed"));

    render(await AdminBenevolatPage());

    expect(screen.queryByTestId("file-benevolat")).not.toBeInTheDocument();
    expect(screen.getByText("Cette page n'a pas pu s'afficher")).toBeInTheDocument();
  });
});
