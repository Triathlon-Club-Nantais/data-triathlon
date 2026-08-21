import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { PendingProvider, SessionUser } from "@/lib/types";

const { listPendingProviders, markProviderHandled, getSession } = vi.hoisted(() => ({
  listPendingProviders: vi.fn(),
  markProviderHandled: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listPendingProviders, markProviderHandled, getSession },
  };
});

import { PendingProvidersTable } from "./PendingProvidersTable";

/** Les deux pouvoirs des signalements sont distincts et attribuables séparément. */
const MODERATEUR: SessionUser = {
  id: 1,
  email: "moi@exemple.fr",
  display_name: "Moi",
  created_at: "2026-01-01T00:00:00Z",
  permissions: ["pending_providers:read", "pending_providers:handle"],
  roles: [],
  groups: [],
};

const LECTEUR: SessionUser = {
  ...MODERATEUR,
  permissions: ["pending_providers:read"],
};

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
    markProviderHandled.mockReset();
    getSession.mockReset();
    getSession.mockResolvedValue(MODERATEUR);
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

  it("offre « Traité » à un porteur de pending_providers:handle", async () => {
    listPendingProviders.mockResolvedValue([SIGNALEMENT]);

    afficher();

    expect(await screen.findByRole("button", { name: /traité/i })).toBeInTheDocument();
  });

  it("n'offre pas « Traité » sans pending_providers:handle", async () => {
    // `pending_providers:read` a ouvert la liste ; le `DELETE` qui retire un
    // signalement exige `pending_providers:handle`, distinct et attribuable
    // séparément. Le bouton offert sans lui ne rend que des 403.
    getSession.mockResolvedValue(LECTEUR);
    listPendingProviders.mockResolvedValue([SIGNALEMENT]);

    afficher();
    await screen.findByText(SIGNALEMENT.url);

    expect(screen.queryByRole("button", { name: /traité/i })).not.toBeInTheDocument();
  });

  it("dit qu'il est en consultation plutôt que de rester muet", async () => {
    getSession.mockResolvedValue(LECTEUR);
    listPendingProviders.mockResolvedValue([SIGNALEMENT]);

    afficher();

    expect(await screen.findByText(/en consultation/i)).toBeInTheDocument();
  });

  it("reste lisible sur une panne réseau", async () => {
    listPendingProviders.mockRejectedValue(new Error("boom"));

    afficher();

    expect(await screen.findByText(/liste indisponible/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun fournisseur signalé/i)).not.toBeInTheDocument();
  });
});
