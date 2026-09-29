import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ImportProgressEvent } from "@/lib/types";

const { importEventStream, push, refresh, toast } = vi.hoisted(() => ({
  importEventStream: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
  toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), message: vi.fn() },
}));

vi.mock("@/lib/api/sse", () => ({ importEventStream }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));
vi.mock("sonner", () => ({ toast }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      detectProvider: vi.fn().mockResolvedValue({ provider: "klikego", supported: true }),
      listProviders: vi.fn().mockResolvedValue(["klikego"]),
      reportPendingProvider: vi.fn().mockResolvedValue({}),
    },
  };
});

import { ImportStreamProvider } from "./ImportStreamProvider";
import { TcnScrapeForm } from "./TcnScrapeForm";

const URL_KLIKEGO = "https://www.klikego.com/resultats/x/42";

/** Un flux SSE qui ne rend sa fin que sur `terminer(...)`. */
function fluxPilote() {
  let terminer!: (fin: ImportProgressEvent) => void;
  const fin = new Promise<ImportProgressEvent>((resolve) => {
    terminer = resolve;
  });
  async function* flux(): AsyncGenerator<ImportProgressEvent> {
    yield { phase: "scraping", message: "Récupération des participants…" } as ImportProgressEvent;
    yield await fin;
  }
  return { flux, terminer };
}

function Page({ formulaire }: { formulaire: boolean }) {
  return formulaire ? <TcnScrapeForm /> : <p>ailleurs</p>;
}

function monter() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const arbre = (formulaire: boolean) => (
    <QueryClientProvider client={client}>
      <ImportStreamProvider>
        <Page formulaire={formulaire} />
      </ImportStreamProvider>
    </QueryClientProvider>
  );
  const rendu = render(arbre(true));
  return { naviguer: (formulaire: boolean) => rendu.rerender(arbre(formulaire)) };
}

async function lancer() {
  fireEvent.change(screen.getByRole("textbox", { name: /Adresse des résultats/ }), {
    target: { value: URL_KLIKEGO },
  });
  const bouton = screen.getByRole("button", { name: /Enregistrer les résultats/ });
  await waitFor(() => expect(bouton).toBeEnabled());
  fireEvent.click(bouton);
  await waitFor(() => expect(importEventStream).toHaveBeenCalledTimes(1));
}

const FIN: ImportProgressEvent = {
  phase: "done",
  total: 120,
  imported: 118,
  updated: 2,
  skipped: 0,
  courses: [{ id: 7, name: "Triathlon de Nantes", event_type: "triathlon-m", event_date: "2026-05-16" }],
} as unknown as ImportProgressEvent;

beforeEach(() => {
  vi.clearAllMocks();
});

// #1062 : quitter `/ajouter` pendant un import ne le coupe plus ; sa fin
// s'annonce par un toast global, et la même URL ne se relance pas.
describe("ImportStreamProvider — l'import survit à la navigation", () => {
  it("annonce la fin par un toast menant à l'épreuve quand le formulaire est démonté", async () => {
    const { flux, terminer } = fluxPilote();
    importEventStream.mockReturnValue(flux());
    const { naviguer } = monter();
    await lancer();

    naviguer(false);
    await act(async () => terminer(FIN));

    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1));
    const [titre, options] = toast.success.mock.calls[0];
    expect(titre).toBe("Import terminé");
    expect(options.action.label).toBe("Voir l'épreuve");
    options.action.onClick();
    expect(push).toHaveBeenCalledWith("/courses/7");
  });

  it("annonce un import partiel, séries perdues comprises", async () => {
    const { flux, terminer } = fluxPilote();
    importEventStream.mockReturnValue(flux());
    const { naviguer } = monter();
    await lancer();

    naviguer(false);
    await act(async () =>
      terminer({
        ...FIN,
        heats_enumerated: 12,
        heats_failed: 3,
        failures: ["a", "b", "c"].map((heat_slug) => ({ heat_slug, reason: "x" })),
      } as unknown as ImportProgressEvent),
    );

    await waitFor(() => expect(toast.warning).toHaveBeenCalledTimes(1));
    const [titre, options] = toast.warning.mock.calls[0];
    expect(titre).toBe("Import partiel");
    expect(options.description).toMatch(/3 séries sur 12/);
    expect(options.action.label).toBe("Voir l'épreuve");
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("annonce l'échec quand le formulaire est démonté", async () => {
    const { flux, terminer } = fluxPilote();
    importEventStream.mockReturnValue(flux());
    const { naviguer } = monter();
    await lancer();

    naviguer(false);
    await act(async () => terminer({ phase: "error", message: "Page illisible" } as ImportProgressEvent));

    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    expect(toast.error.mock.calls[0][0]).toBe("L'import a échoué");
  });

  it("remonte le formulaire sur l'import en cours et n'en relance pas un second", async () => {
    const { flux, terminer } = fluxPilote();
    importEventStream.mockReturnValue(flux());
    const { naviguer } = monter();
    await lancer();

    naviguer(false);
    naviguer(true);

    expect(screen.getByRole("textbox", { name: /Adresse des résultats/ })).toHaveValue(URL_KLIKEGO);
    expect(screen.getByRole("button", { name: /Annuler l'import/ })).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("textbox", { name: /Adresse des résultats/ }), { key: "Enter" });
    expect(importEventStream).toHaveBeenCalledTimes(1);

    // Revenu sur l'écran, c'est lui qui rend le bilan : pas de toast global.
    await act(async () => terminer(FIN));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("prévient avant de fermer l'onglet tant que l'import tourne, formulaire démonté compris", async () => {
    const { flux, terminer } = fluxPilote();
    importEventStream.mockReturnValue(flux());
    const { naviguer } = monter();
    const avant = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(avant);
    expect(avant.defaultPrevented).toBe(false);

    await lancer();
    naviguer(false);
    const pendant = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(pendant);
    expect(pendant.defaultPrevented).toBe(true);

    await act(async () => terminer(FIN));
    const apres = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(apres);
    expect(apres.defaultPrevented).toBe(false);
  });

  it("ne coupe pas le flux au démontage du formulaire", async () => {
    const { flux, terminer } = fluxPilote();
    let signal: AbortSignal | undefined;
    importEventStream.mockImplementation((_url: string, s: AbortSignal) => {
      signal = s;
      return flux();
    });
    const { naviguer } = monter();
    await lancer();

    naviguer(false);

    expect(signal?.aborted).toBe(false);
    await act(async () => terminer(FIN));
  });
});
