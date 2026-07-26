import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/client", () => ({
  apiClient: { detectProvider: vi.fn() },
}));

import { ProviderDetector } from "./ProviderDetector";
import { apiClient } from "@/lib/api/client";

const detectProvider = vi.mocked(apiClient.detectProvider);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ProviderDetector", () => {
  it("annonce le fournisseur que l'API déclare supporté", async () => {
    // Régression : « Non supporté (competitor) » s'affichait sur une URL
    // ironman.com alors que l'import fonctionnait, le composant portant sa
    // propre liste de providers figée à six noms.
    detectProvider.mockResolvedValue({ provider: "competitor", supported: true });
    render(<ProviderDetector url="https://www.ironman.com/races/im703-vichy/results" />);

    await waitFor(() =>
      expect(
        screen.getByText("Fournisseur : IRONMAN (Competitor)"),
      ).toBeInTheDocument(),
    );
  });

  it("bascule sur la saisie manuelle quand l'API déclare l'URL non supportée", async () => {
    detectProvider.mockResolvedValue({ provider: "playwright", supported: false });
    render(<ProviderDetector url="https://chronopuce.test/x" />);

    await waitFor(() =>
      expect(
        screen.getByText("Non supporté (playwright) — saisie manuelle"),
      ).toBeInTheDocument(),
    );
  });

  it("déduit le support du provider si l'API ne le renseigne pas", async () => {
    // Le front peut être déployé avant le backend : sans champ `supported`,
    // seul `playwright` doit passer pour non supporté.
    detectProvider.mockResolvedValue({ provider: "chronoplace" } as {
      provider: string;
      supported?: boolean;
    });
    render(<ProviderDetector url="https://chronoplace.fr/evenement/x" />);

    await waitFor(() =>
      expect(screen.getByText("Fournisseur : Chronoplace")).toBeInTheDocument(),
    );
  });
});
