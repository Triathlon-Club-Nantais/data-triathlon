import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { PendingProvider } from "@/lib/types";

const { listPendingProviders, markProviderHandled } = vi.hoisted(() => ({
  listPendingProviders: vi.fn(),
  markProviderHandled: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listPendingProviders, markProviderHandled },
  };
});

import { PendingProvidersTable } from "./PendingProvidersTable";

const SIGNALEMENT: PendingProvider = {
  id: 1,
  url: "https://inconnu.example/resultats",
  provider_hint: "inconnu.example",
  reported_at: "2026-08-01T14:54:28Z",
};

function afficher() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <PendingProvidersTable />
    </QueryClientProvider>,
  );
}

describe("PendingProvidersTable", () => {
  beforeEach(() => {
    listPendingProviders.mockReset();
  });

  it("affiche les signalements", async () => {
    listPendingProviders.mockResolvedValue([SIGNALEMENT]);

    afficher();

    expect(await screen.findByText(SIGNALEMENT.url)).toBeInTheDocument();
  });

  it("dit « aucun signalement » sur une liste vide", async () => {
    listPendingProviders.mockResolvedValue([]);

    afficher();

    expect(await screen.findByText(/aucun fournisseur signalé/i)).toBeInTheDocument();
  });

  it("dit « accès refusé » sur un 403, et non « aucun signalement »", async () => {
    // Le défaut que ce test ferme : sur un refus, `data` est `undefined`, et le
    // composant concluait « rien à traiter ». Un écran qui ment est pire qu'un
    // écran en erreur — le modérateur mal composé n'a aucun moyen de le savoir.
    listPendingProviders.mockRejectedValue(new ApiError(403, "Refusé"));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun fournisseur signalé/i)).not.toBeInTheDocument();
  });

  it("distingue la session expirée du refus de droit", async () => {
    listPendingProviders.mockRejectedValue(new ApiError(401, "Non connecté"));

    afficher();

    expect(await screen.findByText(/session expirée/i)).toBeInTheDocument();
    expect(screen.queryByText(/accès refusé/i)).not.toBeInTheDocument();
  });

  it("reste lisible sur une panne réseau", async () => {
    listPendingProviders.mockRejectedValue(new Error("boom"));

    afficher();

    expect(await screen.findByText(/liste indisponible/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun fournisseur signalé/i)).not.toBeInTheDocument();
  });
});
