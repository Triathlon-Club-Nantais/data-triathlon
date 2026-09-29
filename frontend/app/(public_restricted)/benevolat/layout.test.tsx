import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getSession } = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("@/lib/api/server", () => ({ apiServer: { getSession } }));

import BenevolatLayout from "./layout";

const session = (permissions: string[]) => ({
  id: 1,
  email: "membre@exemple.fr",
  display_name: "Membre",
  created_at: "2026-09-01T00:00:00Z",
  permissions,
  roles: [],
  groups: [],
  can_administer: false,
});

beforeEach(() => vi.clearAllMocks());

// #879 : le bénévolat passe derrière `pages:preview`, comme la Carte ; rien n'est supprimé.
describe("BenevolatLayout", () => {
  it.each([
    ["anonyme", null],
    ["connecté sans pages:preview", session(["courses:write"])],
  ])("rend le refus à la place de la page pour un visiteur %s", async (_cas, courante) => {
    getSession.mockResolvedValue(courante);

    render(await BenevolatLayout({ children: <p>formulaire</p> }));

    expect(screen.queryByText("formulaire")).not.toBeInTheDocument();
    expect(screen.getByText("Vous n'avez pas la permission nécessaire")).toBeInTheDocument();
  });

  it("rend la page à qui porte pages:preview", async () => {
    getSession.mockResolvedValue(session(["pages:preview"]));

    render(await BenevolatLayout({ children: <p>formulaire</p> }));

    expect(screen.getByText("formulaire")).toBeInTheDocument();
  });
});
