import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import { ApiError } from "@/lib/api/client";
import type { BatchRun, SessionUser } from "@/lib/types";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const { launchBatch, listBatchRuns, getSession, listProviders } = vi.hoisted(() => ({
  launchBatch: vi.fn(),
  listBatchRuns: vi.fn(),
  getSession: vi.fn(),
  listProviders: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { launchBatch, listBatchRuns, getSession, listProviders },
  };
});

import { BatchLauncher } from "./BatchLauncher";

const SESSION = (permissions: string[]): SessionUser =>
  ({
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    roles: [],
    permissions,
  }) as unknown as SessionUser;

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

function afficher() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <BatchLauncher />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getSession.mockResolvedValue(SESSION(["batch:run", "batch:read"]));
  listBatchRuns.mockResolvedValue([]);
  listProviders.mockResolvedValue(["klikego", "chronoplace", "oktime"]);
  launchBatch.mockResolvedValue({ correlation_id: "b7c1f2e4", state: "pending" });
});

describe("BatchLauncher", () => {
  it("lance une reprise avec les filtres saisis", async () => {
    const user = userEvent.setup();
    afficher();

    // Le fournisseur se choisit dans la liste du registre backend, affichée
    // sous son nom commercial ; c'est le slug qui part au lancement.
    await user.click(await screen.findByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Klikego" }));
    await user.type(screen.getByLabelText(/nombre maximum/i), "50");
    await user.click(screen.getByLabelText(/simulation/i));
    await user.click(screen.getByRole("button", { name: /lancer/i }));

    await waitFor(() =>
      expect(launchBatch).toHaveBeenCalledWith({
        mode: "rescrape",
        provider: "klikego",
        limit: 50,
        dry_run: true,
      }),
    );
  });

  it("n'envoie pas les filtres laissés vides", async () => {
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /lancer/i }));

    await waitFor(() =>
      expect(launchBatch).toHaveBeenCalledWith({ mode: "rescrape", dry_run: false }),
    );
  });

  it("n'envoie jamais la base visée", async () => {
    // Elle vient du réglage de l'instance. Un champ ici permettrait à
    // l'administration de la preview d'écrire chez les adhérents.
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /lancer/i }));

    await waitFor(() => expect(launchBatch).toHaveBeenCalled());
    expect(launchBatch.mock.calls[0][0]).not.toHaveProperty("target");
    expect(screen.queryByLabelText(/base|cible|production/i)).toBeNull();
  });

  it("désactive le lancement pendant qu'une exécution tourne", async () => {
    listBatchRuns.mockResolvedValue([RUN({ state: "running", outcome: null })]);
    afficher();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /lancer/i })).toBeDisabled(),
    );
  });

  it("réaffiche le message du serveur tel qu'il est rendu", async () => {
    // Le backend nomme le fournisseur fautif et énumère les connus. Le
    // réécrire ici perdrait exactement ce qui rend l'erreur réparable.
    const message =
      "Fournisseur inconnu : « kliego ». Connus : klikego, chronoplace, oktime.";
    launchBatch.mockRejectedValue(new ApiError(422, message));
    const user = userEvent.setup();
    afficher();

    await user.click(await screen.findByRole("button", { name: /lancer/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
  });

  it("n'interroge pas la liste sans le pouvoir de la lire", async () => {
    // Un porteur de `batch:run` seul verrait sinon un bloc en 403 à la place
    // de l'état courant.
    getSession.mockResolvedValue(SESSION(["batch:run"]));
    afficher();

    await screen.findByRole("button", { name: /lancer/i });
    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(listBatchRuns).not.toHaveBeenCalled();
  });
});
