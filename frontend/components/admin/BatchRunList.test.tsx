import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { BatchReport, BatchRun, SessionUser } from "@/lib/types";

const { listBatchRuns, getBatchReport, getSession } = vi.hoisted(() => ({
  listBatchRuns: vi.fn(),
  getBatchReport: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { listBatchRuns, getBatchReport, getSession } };
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

const SESSION = (permissions: string[]): SessionUser =>
  ({
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    roles: [],
    permissions,
  }) as unknown as SessionUser;

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(MAINTENANT);
  getBatchReport.mockResolvedValue(BILAN);
  getSession.mockResolvedValue(SESSION(["batch:run", "batch:read"]));
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

  it("garde l'heure du démarrage et dit depuis combien de temps", async () => {
    // Deux lancements du même jour étaient indiscernables : `formatDate`
    // coupait l'horodatage aux dix premiers caractères (ADM-3).
    listBatchRuns.mockResolvedValue([
      RUN({ started_at: "2026-08-08T17:45:23Z" }),
    ]);
    afficher();

    const cellule = await screen.findByTestId("demarrage-1284");
    expect(cellule).toHaveTextContent(/08\/08\/2026/);
    expect(cellule).toHaveTextContent(/\d{2}:\d{2}/);
    expect(cellule).toHaveTextContent(/il y a 2 heures/);
  });

  it("ne perd pas tout le tableau sur un horodatage illisible", async () => {
    // `Intl.RelativeTimeFormat.format(NaN)` lève : sans garde, la ligne fautive
    // emportait la liste entière, lignes saines comprises.
    listBatchRuns.mockResolvedValue([
      RUN({ id: 1, started_at: "pas une date", duration_s: null }),
      RUN({ id: 2, label: "batch · sain" }),
    ]);
    afficher();

    expect(await screen.findByText("batch · sain")).toBeInTheDocument();
    expect(screen.getByTestId("duree-1")).toHaveTextContent("—");
  });

  it("dit « à l'instant » sur un lancement qui vient de partir", async () => {
    // L'état juste après le clic. `numeric: "auto"` rendait « cette minute-ci ».
    listBatchRuns.mockResolvedValue([
      RUN({ state: "pending", outcome: null, duration_s: null, started_at: MAINTENANT.toISOString() }),
    ]);
    afficher();

    expect(await screen.findByTestId("demarrage-1284")).toHaveTextContent(
      "à l'instant",
    );
  });

  it("compte la durée écoulée tant que le lancement tourne", async () => {
    // `duration_s` reste nul pendant toute l'exécution : sans ce calcul, la
    // colonne affichait « — » deux heures durant.
    listBatchRuns.mockResolvedValue([
      RUN({
        state: "running",
        outcome: null,
        duration_s: null,
        started_at: "2026-08-08T19:38:00Z",
      }),
    ]);
    afficher();

    expect(await screen.findByTestId("duree-1284")).toHaveTextContent("22 min");
  });

  it("distingue à l'œil un échec d'une réussite", async () => {
    listBatchRuns.mockResolvedValue([
      RUN({ id: 1, outcome: "success" }),
      RUN({ id: 2, outcome: "failure" }),
      RUN({ id: 3, outcome: "cancelled" }),
    ]);
    afficher();

    const reussi = await screen.findByText("Réussi");
    const echec = screen.getByText("Échec");
    const annule = screen.getByText("Annulé");
    expect(echec.className).toMatch(/destructive/);
    expect(reussi.className).not.toBe(echec.className);
    expect(annule.className).not.toBe(echec.className);
    expect(annule.className).not.toBe(reussi.className);
  });

  it("renvoie à l'exécution sans attendre qu'elle se coince", async () => {
    listBatchRuns.mockResolvedValue([RUN()]);
    afficher();

    const lien = await screen.findByRole("link", { name: /voir l'exécution/i });
    expect(lien).toHaveAttribute("href", RUN().external_url);
  });

  it("dit qu'aucun lancement n'a eu lieu quand la liste est vide", async () => {
    listBatchRuns.mockResolvedValue([]);
    afficher();

    expect(await screen.findByText(/aucun lancement/i)).toBeInTheDocument();
  });

  it("n'interroge pas la liste sans `batch:read`, et dit ce qui manque", async () => {
    // L'écran est annoncé sur `batch:run` : ce porteur-là est légitime, et
    // l'appeler quand même lui rendait un bloc d'erreur en 403 (ADM-2).
    getSession.mockResolvedValue(SESSION(["batch:run"]));
    afficher();

    expect(await screen.findByText(/Consulter les batches/)).toBeInTheDocument();
    expect(listBatchRuns).not.toHaveBeenCalled();
    expect(screen.queryByText(/aucun lancement/i)).toBeNull();
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
