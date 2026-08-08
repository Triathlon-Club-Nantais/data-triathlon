import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";

const { revokeSessions, toastError, toastSuccess, push } = vi.hoisted(() => ({
  revokeSessions: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
  push: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { revokeSessions } };
});

import { RevokeSessionsCard } from "./RevokeSessionsCard";

let client: QueryClient;

function afficher() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RevokeSessionsCard />
    </QueryClientProvider>,
  );
}

describe("RevokeSessionsCard (#169)", () => {
  beforeEach(() => {
    revokeSessions.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
    push.mockReset();
  });

  it("ne révoque rien sans confirmation", async () => {
    afficher();

    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    expect(revokeSessions).not.toHaveBeenCalled();
  });

  it("prévient que la session de l'opérateur tombera aussi", async () => {
    afficher();

    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    expect(await screen.findByRole("dialog")).toHaveTextContent(/la vôtre/i);
  });

  it("renoncer laisse toutes les sessions ouvertes", async () => {
    afficher();
    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    await userEvent.click(await screen.findByRole("button", { name: /renoncer/i }));

    expect(revokeSessions).not.toHaveBeenCalled();
  });

  it("confirmé, révoque et annonce les deux unités du bilan", async () => {
    revokeSessions.mockResolvedValue({ sessions: 14, accounts: 3 });
    afficher();
    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    await userEvent.click(await screen.findByRole("button", { name: /révoquer/i }));

    await waitFor(() => expect(revokeSessions).toHaveBeenCalledWith(undefined));
    expect(toastSuccess).toHaveBeenCalledWith(expect.stringMatching(/14.*3/));
  });

  it("renvoie vers la connexion, la session de l'opérateur venant de tomber", async () => {
    revokeSessions.mockResolvedValue({ sessions: 1, accounts: 1 });
    afficher();
    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    await userEvent.click(await screen.findByRole("button", { name: /révoquer/i }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
  });

  it("un refus de l'API laisse l'écran en place et le dit", async () => {
    revokeSessions.mockRejectedValue(new ApiError(403, "Accès refusé"));
    afficher();
    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    await userEvent.click(await screen.findByRole("button", { name: /révoquer/i }));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(push).not.toHaveBeenCalled();
  });

  it("invalide la session en cache : la topbar ne doit pas rester connectée", async () => {
    // `router.push` est une navigation **client** : `AppNav` et `UserMenu`
    // vivent dans le layout racine et ne se démontent pas. Sans invalidation,
    // on atterrit sur /login avec son nom, son avatar et tout le menu
    // d'administration — l'écran d'apparence connectée que ce composant existe
    // pour éviter. `useSession` rend `null` sur 401, jamais une erreur : le
    // refetch donne l'état anonyme correct, comme pour `useLogout`.
    revokeSessions.mockResolvedValue({ sessions: 2, accounts: 2 });
    afficher();
    const invalider = vi.spyOn(client, "invalidateQueries");
    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    await userEvent.click(await screen.findByRole("button", { name: /révoquer/i }));

    await waitFor(() =>
      expect(invalider).toHaveBeenCalledWith({ queryKey: ["session"] }),
    );
  });

  it("un 401 ne laisse pas croire que rien ne s'est passé", async () => {
    // La réponse peut se perdre après le commit (réveil à froid Render, 502,
    // onglet fermé) : le geste a alors bien eu lieu, et le jeton de l'appelant
    // est mort — tout réessai rendra 401, jamais « déjà fait ». Rester sur un
    // écran d'apparence connectée en disant « échec » serait le pire des deux
    // mensonges.
    revokeSessions.mockRejectedValue(new ApiError(401, "Session expirée"));
    afficher();
    await userEvent.click(screen.getByRole("button", { name: /fermer toutes les sessions/i }));

    await userEvent.click(await screen.findByRole("button", { name: /révoquer/i }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
  });
});
