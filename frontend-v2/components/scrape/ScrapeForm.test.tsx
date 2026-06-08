import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock contrôlable du hook d'import (état mutable + spies).
const importMock = vi.hoisted(() => {
  let state = {
    running: false,
    phase: "idle" as string,
    message: "",
    total: 0,
    progress: 0,
    imported: 0,
    skipped: 0,
    cached: false,
    error: null as string | null,
  };
  return {
    start: vi.fn(),
    reset: vi.fn(),
    get: () => state,
    set: (patch: Partial<typeof state>) => {
      state = { ...state, ...patch };
    },
  };
});

vi.mock("@/hooks/useImportStream", () => ({
  useImportStream: () => ({
    state: importMock.get(),
    start: importMock.start,
    reset: importMock.reset,
  }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    detectProvider: vi.fn().mockResolvedValue({ provider: "klikego" }),
    reportPendingProvider: vi.fn().mockResolvedValue({}),
    saveParticipation: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { ScrapeForm } from "./ScrapeForm";
import { apiClient } from "@/lib/api/client";

function renderForm() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={qc}>
      <ScrapeForm />
    </QueryClientProvider>,
  );
  return {
    ...utils,
    rerenderForm: () =>
      utils.rerender(
        <QueryClientProvider client={qc}>
          <ScrapeForm />
        </QueryClientProvider>,
      ),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  importMock.set({ running: false, phase: "idle", error: null });
});

describe("ScrapeForm (event-only)", () => {
  it("ne propose plus le champ Dossard ni le bouton Analyser de l'étape source", () => {
    renderForm();
    expect(screen.queryByText("Dossard (optionnel)")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Analyser" }),
    ).not.toBeInTheDocument();
  });

  it("lance l'import direct de l'épreuve au clic", async () => {
    renderForm();
    await userEvent.type(
      screen.getByPlaceholderText("https://…"),
      "http://klikego.test/ev",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Importer l'épreuve" }),
    );
    expect(importMock.start).toHaveBeenCalledWith("http://klikego.test/ev");
  });

  it("ouvre la saisie manuelle au clic sur le bouton dédié", async () => {
    renderForm();
    await userEvent.click(
      screen.getByRole("button", { name: "Saisie manuelle" }),
    );
    expect(
      screen.getByRole("button", { name: "Enregistrer le résultat" }),
    ).toBeInTheDocument();
  });

  it("sur échec d'import, signale le fournisseur et bascule en saisie manuelle", async () => {
    const { rerenderForm } = renderForm();
    await userEvent.type(
      screen.getByPlaceholderText("https://…"),
      "http://x.test/ev",
    );
    importMock.set({ phase: "error", error: "boom" });
    rerenderForm();
    await waitFor(() =>
      expect(apiClient.reportPendingProvider).toHaveBeenCalledWith(
        "http://x.test/ev",
      ),
    );
    expect(
      screen.getByRole("button", { name: "Enregistrer le résultat" }),
    ).toBeInTheDocument();
  });
});
