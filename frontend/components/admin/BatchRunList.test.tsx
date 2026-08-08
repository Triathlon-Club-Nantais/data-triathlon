import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { BatchReport, BatchRun } from "@/lib/types";

const { listBatchRuns, getBatchReport } = vi.hoisted(() => ({
  listBatchRuns: vi.fn(),
  getBatchReport: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listBatchRuns, getBatchReport } };
});

import { BatchRunList } from "./BatchRunList";

const MAINTENANT = new Date("2026-08-08T20:00:00Z");

const RUN = (surcharges: Partial<BatchRun> = {}): BatchRun => ({
  id: 1284,
  label: "batch · production · rescrape · b7c1f2e4",
  state: "completed",
  outcome: "success",
  started_at: "2026-08-08T18:00:23Z",
  duration_s: 240,
  triggered_by: "ui",
  report_available: true,
  external_url: "https://github.com/un-club/un-depot/actions/runs/1284",
  ...surcharges,
});

const BILAN: BatchReport = {
  unique_supported: 117,
  processed: 117,
  errors: 3,
  imported: 2841,
  updated: 96,
  skipped: 15230,
  interrupted: false,
  failures: [{ url: "https://x.test/r", label: "klikego · x", message: "HTTP 503" }],
};

function afficher() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <BatchRunList />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(MAINTENANT);
  getBatchReport.mockResolvedValue(BILAN);
});

describe("BatchRunList", () => {
  it("traduit les trois états à l'affichage", async () => {
    listBatchRuns.mockResolvedValue([
      RUN({ id: 1, state: "pending", outcome: null }),
      RUN({ id: 2, state: "running", outcome: null }),
      RUN({ id: 3, state: "completed", outcome: "success" }),
    ]);
    afficher();

    expect(await screen.findByText("En attente")).toBeInTheDocument();
    expect(screen.getByText("En cours")).toBeInTheDocument();
    expect(screen.getByText("Réussi")).toBeInTheDocument();
  });

  it("renvoie au bilan sur un échec, sans en affirmer la cause", async () => {
    // `failure` recouvre trois causes que seul le bilan distingue : échec total
    // du batch, erreur d'usage, ou panne d'infrastructure avant la commande.
    listBatchRuns.mockResolvedValue([RUN({ outcome: "failure" })]);
    afficher();

    expect(await screen.findByText("Échec")).toBeInTheDocument();
    expect(screen.queryByText(/toutes les épreuves/i)).toBeNull();
    expect(screen.getByRole("button", { name: /bilan/i })).toBeEnabled();
  });

  it("distingue un bilan indisponible d'un bilan vide", async () => {
    listBatchRuns.mockResolvedValue([
      RUN({ outcome: "failure", report_available: false }),
    ]);
    afficher();

    await screen.findByText("Échec");
    expect(screen.queryByRole("button", { name: /bilan/i })).toBeNull();
    expect(screen.getByText(/aucun bilan/i)).toBeInTheDocument();
  });

  it("nomme les unités des compteurs du bilan", async () => {
    listBatchRuns.mockResolvedValue([RUN()]);
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /bilan/i }));

    const epreuves = await screen.findByTestId("compteurs-epreuves");
    expect(epreuves).toHaveTextContent(/épreuves/i);
    expect(epreuves).toHaveTextContent("117");
    const participants = screen.getByTestId("compteurs-participants");
    expect(participants).toHaveTextContent(/participants/i);
    expect(participants).toHaveTextContent("2841");
  });

  it("affiche le message du serveur quand le bilan a expiré", async () => {
    listBatchRuns.mockResolvedValue([RUN()]);
    getBatchReport.mockRejectedValue(
      new ApiError(410, "Le bilan de ce lancement a expiré."),
    );
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /bilan/i }));

    expect(await screen.findByText(/a expiré/i)).toBeInTheDocument();
  });

  it("signale une exécution en cours depuis plus de deux heures", async () => {
    // Le workflow borne à 120 minutes ; au-delà, quelque chose est coincé et
    // le seul geste utile est de l'annuler sur sa page.
    listBatchRuns.mockResolvedValue([
      RUN({ state: "running", outcome: null, started_at: "2026-08-08T17:30:00Z" }),
    ]);
    afficher();

    expect(await screen.findByText(/plus de deux heures/i)).toBeInTheDocument();
    const lien = screen.getByRole("link", { name: /annuler/i });
    expect(lien).toHaveAttribute("href", RUN().external_url);
  });

  it("ne signale pas une exécution en cours depuis dix minutes", async () => {
    listBatchRuns.mockResolvedValue([
      RUN({ state: "running", outcome: null, started_at: "2026-08-08T19:50:00Z" }),
    ]);
    afficher();

    await screen.findByText("En cours");
    expect(screen.queryByText(/plus de deux heures/i)).toBeNull();
  });

  it("dit qu'aucun lancement n'a eu lieu quand la liste est vide", async () => {
    listBatchRuns.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText(/aucun lancement/i)).toBeInTheDocument();
  });

  it("ne confond pas une plateforme injoignable avec une liste vide", async () => {
    listBatchRuns.mockRejectedValue(
      new ApiError(503, "La plateforme d'exécution des batches est injoignable."),
    );
    afficher();

    expect(await screen.findByText(/injoignable/i)).toBeInTheDocument();
    expect(screen.queryByText(/aucun lancement/i)).toBeNull();
  });
});
