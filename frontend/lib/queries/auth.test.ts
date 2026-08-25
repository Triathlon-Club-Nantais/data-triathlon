import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { useAuthMethods, useSession } from "@/lib/queries/auth";

const { getSession, listAuthMethods } = vi.hoisted(() => ({
  getSession: vi.fn(),
  listAuthMethods: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, listAuthMethods } };
});

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return createElement(QueryClientProvider, { client }, children);
}

describe("useSession", () => {
  it("rend l'utilisateur quand une session est ouverte", async () => {
    getSession.mockResolvedValue({
      id: 1,
      email: "contributeur@exemple.fr",
      display_name: "contributeur",
      created_at: "2026-08-01T14:54:28Z",
    });

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.data?.email).toBe("contributeur@exemple.fr");
    expect(result.current.isError).toBe(false);
  });

  it("rend null sur 401 sans propager d'erreur", async () => {
    // Anonyme est un **état normal** de la page, pas une panne : propager
    // l'erreur ferait clignoter un message d'échec sur chaque visite anonyme.
    getSession.mockRejectedValue(new ApiError(401, "Vous devez être connecté."));

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.isError).toBe(false);
  });

  it("laisse remonter une vraie panne", async () => {
    getSession.mockRejectedValue(new ApiError(500, "Boum"));

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("rend null sans appeler l'API quand aucun cookie de présence n'est posé", async () => {
    // #427 — évite le 401 systématique loggé par le navigateur pour tout
    // visiteur anonyme : la grande majorité du trafic d'un site public.
    document.cookie = "tcn_logged_in=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
    getSession.mockClear();
    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.data).toBeNull();
    expect(getSession).not.toHaveBeenCalled();
  });
});

describe("useAuthMethods", () => {
  it("rend les méthodes déclarées par le backend", async () => {
    listAuthMethods.mockResolvedValue([{ slug: "github", label: "GitHub" }]);

    const { result } = renderHook(() => useAuthMethods(), { wrapper });

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.data).toEqual([{ slug: "github", label: "GitHub" }]);
  });

  it("traite une liste vide comme une réponse valide", async () => {
    listAuthMethods.mockResolvedValue([]);

    const { result } = renderHook(() => useAuthMethods(), { wrapper });

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.data).toEqual([]);
    expect(result.current.isError).toBe(false);
  });

  it("ne réessaie pas automatiquement : une panne lève isError sans délai (#494)", async () => {
    // Sans `retry: false` porté par le hook lui-même, le défaut de React Query
    // (3 essais, délais croissants) retarde `isError` de plusieurs secondes —
    // exactement le silence que la page de connexion doit rompre. Ce test
    // construit son propre client, sans l'écraser globalement, pour que ce
    // soit bien le hook qui porte le réglage.
    listAuthMethods.mockClear();
    listAuthMethods.mockRejectedValue(new ApiError(500, "boum"));
    const client = new QueryClient();
    const { result } = renderHook(() => useAuthMethods(), {
      wrapper: ({ children }) => createElement(QueryClientProvider, { client }, children),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(listAuthMethods).toHaveBeenCalledTimes(1);
  });
});
