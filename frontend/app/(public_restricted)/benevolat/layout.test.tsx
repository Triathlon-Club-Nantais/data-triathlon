import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { getSession, refresh } = vi.hoisted(() => ({ getSession: vi.fn(), refresh: vi.fn() }));
vi.mock("@/lib/api/server", () => ({ apiServer: { getSession } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }), unstable_rethrow: () => {} }));

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

let journal: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  vi.clearAllMocks();
  journal = vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => journal.mockRestore());

// #879 : les déclarations de crédit passent derrière `pages:preview`, comme la
// Carte ; rien n'est supprimé.
describe("BenevolatLayout", () => {
  it("invite un anonyme à se connecter, sous le vrai en-tête de la page", async () => {
    getSession.mockResolvedValue(null);

    render(await BenevolatLayout({ children: <p>formulaire</p> }));

    expect(screen.queryByText("formulaire")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Créditer un athlète pour le quota de saison" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Se connecter" })).toHaveAttribute("href", "/login");
    expect(screen.queryByText(/votre rôle/)).not.toBeInTheDocument();
  });

  it("dit à un connecté sans pages:preview de demander le pouvoir", async () => {
    getSession.mockResolvedValue(session(["courses:write"]));

    render(await BenevolatLayout({ children: <p>formulaire</p> }));

    expect(screen.queryByText("formulaire")).not.toBeInTheDocument();
    expect(screen.getByText("Vous n'avez pas la permission nécessaire")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Se connecter" })).not.toBeInTheDocument();
  });

  it.each([
    ["un 503", new ApiError(503, "Service Unavailable")],
    ["une coupure réseau", new TypeError("fetch failed")],
  ])("rend l'écran d'indisponibilité du site sur %s, sans planter", async (_cas, erreur) => {
    getSession.mockRejectedValue(erreur);

    render(await BenevolatLayout({ children: <p>formulaire</p> }));

    expect(screen.queryByText("formulaire")).not.toBeInTheDocument();
    expect(screen.getByText("Cette page n'a pas pu s'afficher")).toBeInTheDocument();
    screen.getByRole("button", { name: "Réessayer" }).click();
    expect(refresh).toHaveBeenCalled();
  });

  it("rend la page à qui porte pages:preview", async () => {
    getSession.mockResolvedValue(session(["pages:preview"]));

    render(await BenevolatLayout({ children: <p>formulaire</p> }));

    expect(screen.getByText("formulaire")).toBeInTheDocument();
  });
});
