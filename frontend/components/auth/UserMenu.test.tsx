import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { SessionUser } from "@/lib/types";

const { push, getSession, logout } = vi.hoisted(() => ({
  push: vi.fn(),
  getSession: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push, refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, logout } };
});

import { UserMenu } from "./UserMenu";

const SESSION: SessionUser = {
  id: 1,
  email: "contributeur@exemple.fr",
  display_name: "contributeur",
  created_at: "2026-08-01T14:54:28Z",
  permissions: [],
  roles: [],
};

function afficher(session: SessionUser | null, props: { pleineLargeur?: boolean } = {}) {
  push.mockClear();
  logout.mockClear();
  logout.mockResolvedValue(undefined);
  if (session) getSession.mockResolvedValue(session);
  else getSession.mockRejectedValue(new ApiError(401, "anonyme"));

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <UserMenu {...props} />
    </QueryClientProvider>,
  );
}

/** Ouvre le menu déroulant et rend son contenu. */
async function ouvrirLeMenu() {
  const declencheur = await screen.findByRole("button", { name: /Compte/ });
  await userEvent.click(declencheur);
  return { declencheur, menu: await screen.findByRole("menu") };
}

describe("UserMenu — anonyme (AC5)", () => {
  it("propose « Se connecter », inchangé", async () => {
    afficher(null);

    const bouton = await screen.findByRole("button", { name: "Se connecter" });
    expect(bouton.closest("a")).toBeNull();

    await userEvent.click(bouton);
    expect(push).toHaveBeenCalledWith("/login");
  });

  it("n'expose ni menu ni déconnexion", async () => {
    afficher(null);
    await screen.findByRole("button", { name: "Se connecter" });

    expect(screen.queryByRole("button", { name: /Compte/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Se déconnecter" })).not.toBeInTheDocument();
  });
});

describe("UserMenu — connecté (AC1, AC2, AC3, AC4, AC6)", () => {
  it("ne pose qu'un seul élément d'authentification : le déclencheur (AC1)", async () => {
    afficher(SESSION);

    await screen.findByRole("button", { name: /Compte/ });
    // Ni l'adresse, ni la déconnexion ne s'étalent dans la barre : elles vivent
    // dans le menu, qui n'est pas encore ouvert.
    expect(screen.queryByText(SESSION.email)).not.toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Se déconnecter" })).not.toBeInTheDocument();
  });

  it("nomme le déclencheur avec l'adresse de connexion (AC6)", async () => {
    afficher(SESSION);
    expect(await screen.findByRole("button", { name: `Compte — ${SESSION.email}` })).toBeInTheDocument();
  });

  it("affiche l'adresse en clair dans le menu ouvert, sans survol (AC2)", async () => {
    afficher(SESSION);
    const { menu } = await ouvrirLeMenu();

    expect(menu).toHaveTextContent(SESSION.email);
  });

  it("mène à /admin par un vrai lien (AC3)", async () => {
    afficher(SESSION);
    await ouvrirLeMenu();

    const lien = screen.getByRole("menuitem", { name: "Administration" });
    expect(lien).toHaveAttribute("href", "/admin");
  });

  it("déconnecte depuis le menu et revient à l'accueil (AC4)", async () => {
    afficher(SESSION);
    await ouvrirLeMenu();

    await userEvent.click(screen.getByRole("menuitem", { name: "Se déconnecter" }));

    await waitFor(() => expect(logout).toHaveBeenCalled());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });

  it("se ferme à la touche Échap (AC6)", async () => {
    afficher(SESSION);
    await ouvrirLeMenu();

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
  });
});

describe("UserMenu — tiroir mobile (AC7)", () => {
  it("déplie l'état connecté à plat, sans second déclencheur", async () => {
    afficher(SESSION, { pleineLargeur: true });

    expect(await screen.findByText(SESSION.email)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Administration" })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Compte/ })).not.toBeInTheDocument();
  });

  it("déconnecte depuis le tiroir", async () => {
    afficher(SESSION, { pleineLargeur: true });

    await userEvent.click(await screen.findByRole("button", { name: "Se déconnecter" }));

    await waitFor(() => expect(logout).toHaveBeenCalled());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
  });
});
