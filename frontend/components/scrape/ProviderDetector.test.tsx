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
    // Aucun chronométreur ne reconnaît l'URL : l'API rend `provider: ""`. Le
    // badge ne doit pas nommer de fournisseur — « Non supporté (Source) », le
    // repli de `providerLabel`, serait un faux nom.
    detectProvider.mockResolvedValue({ provider: "", supported: false });
    render(<ProviderDetector url="https://chronopuce.test/x" />);

    await waitFor(() =>
      expect(screen.getByText("Non supporté — saisie manuelle")).toBeInTheDocument(),
    );
  });

  it("signale la détection au parent via onDetected, y compris l'absence de résultat", async () => {
    detectProvider.mockResolvedValue({ provider: "", supported: false });
    const onDetected = vi.fn();
    const { rerender } = render(
      <ProviderDetector url="https://chronopuce.test/x" onDetected={onDetected} />,
    );

    await waitFor(() =>
      expect(onDetected).toHaveBeenCalledWith({ provider: "", supported: false }),
    );

    onDetected.mockClear();
    rerender(<ProviderDetector url="" onDetected={onDetected} />);
    await waitFor(() => expect(onDetected).toHaveBeenCalledWith(null));
  });
});
