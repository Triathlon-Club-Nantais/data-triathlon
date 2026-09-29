import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ImportProgressEvent } from "@/lib/types";

const { importEventStream, push, refresh, toast, reportPendingProvider } = vi.hoisted(() => ({
  importEventStream: vi.fn(),
  push: vi.fn(),
  refresh: vi.fn(),
  toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), message: vi.fn(), dismiss: vi.fn() },
  reportPendingProvider: vi.fn(),
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
      reportPendingProvider,
    },
  };
});

import { ApiError } from "@/lib/api/client";
import { ImportStreamProvider } from "./ImportStreamProvider";
import { TcnScrapeForm } from "./TcnScrapeForm";

const URL_KLIKEGO = "https://www.klikego.com/resultats/x/42";

/** Un flux SSE qui ne rend sa fin que sur `terminer(...)` ou `echouer(...)`. */
function fluxPilote() {
  let terminer!: (fin: ImportProgressEvent) => void;
  let echouer!: (erreur: Error) => void;
  const fin = new Promise<ImportProgressEvent>((resolve, reject) => {
    terminer = resolve;
    echouer = reject;
  });
  async function* flux(): AsyncGenerator<ImportProgressEvent> {
    yield { phase: "scraping", message: "Récupération des participants…" } as ImportProgressEvent;
    yield await fin;
  }
  return { flux, terminer, echouer };
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

/** Lance un import, quitte l'écran, et rend la main pour le terminer. */
async function lancerPuisQuitter() {
  const pilote = fluxPilote();
  importEventStream.mockReturnValue(pilote.flux());
  const { naviguer } = monter();
  await lancer();
  naviguer(false);
  return { ...pilote, naviguer };
}

const TRIATHLON = { id: 7, name: "Triathlon de Nantes", event_type: "triathlon-m", event_date: "2026-05-16" };
const FIN = {
  phase: "done",
  total: 120,
  imported: 118,
  updated: 2,
  skipped: 0,
  courses: [TRIATHLON],
} as unknown as ImportProgressEvent;
const PARTIEL = {
  ...FIN,
  heats_enumerated: 12,
  heats_failed: 3,
  failures: ["a", "b", "c"].map((heat_slug) => ({ heat_slug, reason: "x" })),
} as unknown as ImportProgressEvent;

/** Dernier appel d'un toast : [titre, options]. */
const dernier = (fn: ReturnType<typeof vi.fn>) => fn.mock.calls[fn.mock.calls.length - 1];

beforeEach(() => {
  vi.clearAllMocks();
  reportPendingProvider.mockResolvedValue({});
});

afterEach(() => {
  vi.restoreAllMocks();
});

// #1062 : quitter `/ajouter` pendant un import ne le coupe plus ; sa fin
// s'annonce par un toast global, et la même URL ne se relance pas.
describe("ImportStreamProvider — l'import survit à la navigation", () => {
  it("annonce un succès en nommant l'épreuve, avec « Voir les résultats » et les mots du bilan", async () => {
    const { terminer } = await lancerPuisQuitter();
    await act(async () => terminer(FIN));

    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1));
    const [titre, options] = dernier(toast.success);
    expect(titre).toBe("Résultats enregistrés : « Triathlon de Nantes »");
    expect(options.description).toBe("118 résultats ajoutés · 2 mis à jour · 0 déjà présent");
    expect(options.duration).toBeGreaterThan(4000);
    expect(options.action.label).toBe("Voir les résultats");
    options.action.onClick();
    expect(push).toHaveBeenCalledWith("/courses/7");
    expect(refresh).toHaveBeenCalled();
  });

  it("annonce plusieurs épreuves sans en choisir une, et mène à l'écran d'import", async () => {
    const { terminer } = await lancerPuisQuitter();
    await act(async () =>
      terminer({ ...FIN, courses: [TRIATHLON, { ...TRIATHLON, id: 8, name: "Duathlon" }] } as ImportProgressEvent),
    );

    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1));
    const [titre, options] = dernier(toast.success);
    expect(titre).toBe("Résultats enregistrés : 2 épreuves");
    expect(options.action.label).toBe("Voir les épreuves");
    options.action.onClick();
    expect(push).toHaveBeenCalledWith("/ajouter");
  });

  it("n'annonce pas en vert un import déjà enregistré", async () => {
    const { terminer } = await lancerPuisQuitter();
    await act(async () => terminer({ ...FIN, imported: 0, updated: 0, skipped: 120, cached: true } as ImportProgressEvent));

    await waitFor(() => expect(toast.message).toHaveBeenCalledTimes(1));
    expect(dernier(toast.message)[0]).toBe("Résultats déjà enregistrés");
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("annonce un import partiel qui reste affiché, et le bilan survit au retour sur l'écran", async () => {
    const { terminer, naviguer } = await lancerPuisQuitter();
    await act(async () => terminer(PARTIEL));

    await waitFor(() => expect(toast.warning).toHaveBeenCalledTimes(1));
    const [titre, options] = dernier(toast.warning);
    expect(titre).toBe("Import partiel : « Triathlon de Nantes »");
    expect(options.description).toMatch(/^3 séries sur 12 manquent\./);
    expect(options.duration).toBe(Infinity);
    expect(options.closeButton).toBe(true);

    naviguer(true);
    expect(screen.getByText(/Import partiel : 3 séries sur 12 manquent/)).toBeInTheDocument();
    expect(screen.getByText(/Série « a »/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Relancer l'import" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Adresse des résultats/ })).toHaveValue(URL_KLIKEGO);
    // Le bilan est à l'écran : le toast n'a plus de raison d'y rester.
    expect(toast.dismiss).toHaveBeenCalled();
  });

  it("page illisible : signale le fournisseur et propose la saisie manuelle", async () => {
    const { terminer, naviguer } = await lancerPuisQuitter();
    await act(async () => terminer({ phase: "error", message: "Page illisible" } as ImportProgressEvent));

    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    const [titre, options] = dernier(toast.error);
    expect(titre).toBe("Impossible d'importer automatiquement");
    expect(options.duration).toBe(Infinity);
    expect(options.closeButton).toBe(true);
    expect(options.action.label).toBe("Saisir à la main");
    expect(reportPendingProvider).toHaveBeenCalledTimes(1);
    expect(reportPendingProvider).toHaveBeenCalledWith(URL_KLIKEGO);

    options.action.onClick();
    expect(push).toHaveBeenCalledWith("/ajouter");
    naviguer(true);
    expect(screen.getByRole("button", { name: "Enregistrer votre participation" })).toBeInTheDocument();
    // Déjà signalé par le provider : le formulaire remonté ne le refait pas.
    expect(reportPendingProvider).toHaveBeenCalledTimes(1);
  });

  it("service muet : jamais le message anglais du navigateur, et « Relancer l'import » garde l'URL", async () => {
    const { echouer } = await lancerPuisQuitter();
    await act(async () => echouer(new TypeError("Failed to fetch")));

    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    const [titre, options] = dernier(toast.error);
    expect(titre).toBe("Le service n'a pas répondu");
    expect(options.description).not.toMatch(/Failed to fetch/);
    expect(options.action.label).toBe("Relancer l'import");
    expect(reportPendingProvider).not.toHaveBeenCalled();

    importEventStream.mockReturnValue(fluxPilote().flux());
    options.action.onClick();
    expect(importEventStream).toHaveBeenCalledTimes(2);
    expect(importEventStream.mock.calls[1][0]).toBe(URL_KLIKEGO);
    expect(push).toHaveBeenCalledWith("/ajouter");
  });

  it("plafond de débit : dit le délai d'attente, sans signaler le fournisseur", async () => {
    const { echouer } = await lancerPuisQuitter();
    await act(async () => echouer(new ApiError(429, "Trop de demandes", 180)));

    await waitFor(() => expect(toast.warning).toHaveBeenCalledTimes(1));
    const [titre, options] = dernier(toast.warning);
    expect(titre).toBe("Trop d'imports dans l'heure");
    expect(options.description).toBe("Réessayez dans 3 minutes.");
    expect(toast.error).not.toHaveBeenCalled();
    expect(reportPendingProvider).not.toHaveBeenCalled();
  });

  it("remonte le formulaire sur l'import en cours et n'en relance pas un second", async () => {
    const { terminer, naviguer } = await lancerPuisQuitter();
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

  it("garde l'horloge de l'import au retour sur l'écran, sans repartir de zéro", async () => {
    const { terminer, naviguer } = await lancerPuisQuitter();
    const apresLancement = Date.now();

    vi.spyOn(Date, "now").mockReturnValue(apresLancement + 65_000);
    naviguer(true);

    expect(screen.getByText(/Import en cours depuis 1 min 5 s/)).toBeInTheDocument();
    await act(async () => terminer(FIN));
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
