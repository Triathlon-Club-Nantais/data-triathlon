import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api/client", () => ({
  apiClient: { detectProvider: vi.fn(), listProviders: vi.fn() },
}));

import { ProviderDetector } from "./ProviderDetector";
import { apiClient } from "@/lib/api/client";

const detectProvider = vi.mocked(apiClient.detectProvider);
const listProviders = vi.mocked(apiClient.listProviders);

function afficher(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  listProviders.mockResolvedValue(["klikego", "wiclax", "competitor"]);
});

describe("ProviderDetector — un seul verdict, au même endroit (#492, ACT-6)", () => {
  it("annonce le fournisseur que l'API déclare supporté", async () => {
    // Régression : « Non supporté (competitor) » s'affichait sur une URL
    // ironman.com alors que l'import fonctionnait, le composant portant sa
    // propre liste de providers figée à six noms.
    detectProvider.mockResolvedValue({ provider: "competitor", supported: true });
    afficher(<ProviderDetector url="https://www.ironman.com/races/im703-vichy/results" />);

    expect(
      await screen.findByText("Chronométreur reconnu : IRONMAN (Competitor)"),
    ).toBeInTheDocument();
  });

  it("sur adresse non reconnue, dit une seule fois ce qui se passe et offre la sortie", async () => {
    // Aucun chronométreur ne reconnaît l'URL : l'API rend `provider: ""`. La
    // ligne ne doit nommer aucun fournisseur — « Non supporté (Source) », le
    // repli de `providerLabel`, serait un faux nom.
    detectProvider.mockResolvedValue({ provider: "", supported: false });
    const onSaisieManuelle = vi.fn();
    afficher(
      <ProviderDetector url="https://chronopuce.test/x" onSaisieManuelle={onSaisieManuelle} />,
    );

    expect(
      await screen.findByText("Aucun chronométreur ne reconnaît cette adresse."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Saisir à la main" }));
    expect(onSaisieManuelle).toHaveBeenCalledTimes(1);
  });

  it("signale la détection au parent via onDetected, y compris l'absence de résultat", async () => {
    detectProvider.mockResolvedValue({ provider: "", supported: false });
    const onDetected = vi.fn();
    const { rerender } = afficher(
      <ProviderDetector url="https://chronopuce.test/x" onDetected={onDetected} />,
    );

    await waitFor(() =>
      expect(onDetected).toHaveBeenCalledWith({ provider: "", supported: false }),
    );

    onDetected.mockClear();
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ProviderDetector url="" onDetected={onDetected} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(onDetected).toHaveBeenCalledWith(null));
  });

  it("au repos, nomme les chronométreurs reconnus d'après le registre backend", async () => {
    // Sans liste tenue à la main dans le front : le front en avait déjà tenu
    // une, et elle avait divergé du registre.
    afficher(<ProviderDetector url="" />);

    expect(await screen.findByText("Klikego")).toBeInTheDocument();
    expect(screen.getByText("Wiclax")).toBeInTheDocument();
    expect(screen.getByText("IRONMAN (Competitor)")).toBeInTheDocument();
    expect(apiClient.detectProvider).not.toHaveBeenCalled();
  });

  it("réserve la hauteur de la ligne pendant la détection, pour ne rien décaler", () => {
    detectProvider.mockReturnValue(new Promise(() => {}));
    const { container } = afficher(<ProviderDetector url="https://www.klikego.com/x" />);

    // La ligne existe avant tout verdict : sans elle, le bouton d'import
    // remonterait puis redescendrait à chaque frappe.
    const ligne = container.querySelector("[data-verdict]") as HTMLElement;
    expect(ligne).not.toBeNull();
    expect(ligne.style.minHeight).toBe("22px");
    expect(ligne.textContent).toBe("");
  });
});
