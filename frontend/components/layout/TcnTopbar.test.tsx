import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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
  return {
    ...original,
    apiClient: { listParticipations: vi.fn().mockResolvedValue([]), getSession, logout },
  };
});

import { TcnTopbar } from "./TcnTopbar";

function afficher(session: SessionUser | null) {
  push.mockClear();
  if (session) getSession.mockResolvedValue(session);
  else getSession.mockRejectedValue(new ApiError(401, "anonyme"));

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TcnTopbar />
    </QueryClientProvider>,
  );
}

const SESSION: SessionUser = {
  id: 1,
  email: "contributeur@exemple.fr",
  display_name: "contributeur",
  created_at: "2026-08-01T14:54:28Z",
};

describe("TcnTopbar — visibilité des onglets (issues #10, #28)", () => {
  it("affiche les onglets conservés : Tableau de bord et Résultats", async () => {
    afficher(null);
    expect(screen.getByRole("link", { name: "Tableau de bord" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Résultats" })).toBeInTheDocument();
  });

  it("n'affiche pas les onglets masqués : Club, Carte et Admin", async () => {
    afficher(null);
    expect(screen.queryByRole("link", { name: "Club" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Carte" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });
});

describe("TcnTopbar — session (#114)", () => {
  it("propose « Se connecter » à un visiteur anonyme", async () => {
    afficher(null);

    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Se connecter" }).length).toBeGreaterThan(0),
    );
    expect(screen.queryByText("contributeur")).not.toBeInTheDocument();
  });

  it("mène à /login par le routeur, sans imbriquer le bouton dans un lien", async () => {
    // Un `<a>` enveloppant un `<button>` est un HTML invalide — deux éléments
    // interactifs imbriqués — que les technologies d'assistance annoncent deux
    // fois. La navigation passe donc par le routeur, comme les deux autres
    // actions de cette barre (« Ajouter un triathlon »).
    afficher(null);
    const [bouton] = await screen.findAllByRole("button", { name: "Se connecter" });

    expect(bouton.closest("a")).toBeNull();

    await userEvent.click(bouton);
    expect(push).toHaveBeenCalledWith("/login");
  });

  it("affiche l'utilisateur et la déconnexion quand une session est ouverte", async () => {
    afficher(SESSION);

    await waitFor(() => expect(screen.getAllByText("contributeur").length).toBeGreaterThan(0));
    expect(screen.getAllByRole("button", { name: "Se déconnecter" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Se connecter" })).not.toBeInTheDocument();
  });

  it("pose l'action dans le tiroir mobile aussi", async () => {
    // Toute action de cette barre est déclarée **deux fois** : bloc desktop et
    // tiroir. N'en poser qu'une la rend invisible sur la moitié des appareils.
    afficher(SESSION);
    await waitFor(() => expect(screen.getAllByText("contributeur").length).toBeGreaterThan(0));

    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));

    const tiroir = await screen.findByRole("dialog");
    expect(within(tiroir).getByText("contributeur")).toBeInTheDocument();
    expect(within(tiroir).getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();
  });

  it("propose « Se connecter » dans le tiroir mobile pour un anonyme", async () => {
    afficher(null);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Se connecter" }).length).toBeGreaterThan(0),
    );

    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));

    const tiroir = await screen.findByRole("dialog");
    expect(within(tiroir).getByRole("button", { name: "Se connecter" })).toBeInTheDocument();
  });
});
