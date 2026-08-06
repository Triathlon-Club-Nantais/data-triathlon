import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ImportedCourse } from "@/lib/types";

// Ces tests contrôlent l'état du hook d'import de bout en bout pour n'observer
// que le rendu — l'objectif est de câbler la phase `done` sur /courses/{id} (#135),
// le reste du flux est déjà couvert par ScrapeForm.test.
const importMock = vi.hoisted(() => {
  let state = {
    running: false,
    phase: "idle" as string,
    message: "",
    total: 0,
    progress: 0,
    imported: 0,
    updated: 0,
    skipped: 0,
    cached: false,
    courses: [] as ImportedCourse[],
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

const refreshMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock, push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    detectProvider: vi.fn().mockResolvedValue({ provider: "klikego" }),
    reportPendingProvider: vi.fn().mockResolvedValue({}),
    saveParticipation: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { TcnScrapeForm } from "./TcnScrapeForm";

function renderForm() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <TcnScrapeForm />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  importMock.set({
    running: false,
    phase: "idle",
    imported: 0,
    updated: 0,
    skipped: 0,
    cached: false,
    courses: [],
    error: null,
  });
});

describe("TcnScrapeForm — navigation vers les courses importées (#135)", () => {
  it("solo : rend un bouton primary qui file vers /courses/{id}", () => {
    importMock.set({
      phase: "done",
      imported: 12,
      skipped: 0,
      courses: [
        { id: 42, name: "Triathlon de Nantes 2026", event_type: "triathlon-m" },
      ],
    });
    renderForm();
    const link = screen.getByRole("link", {
      name: /Voir les résultats de « Triathlon de Nantes 2026 »/,
    });
    expect(link.getAttribute("href")).toBe("/courses/42");
  });

  it("multi : rend un sélecteur, avec la 1re course pré-sélectionnée", () => {
    importMock.set({
      phase: "done",
      imported: 300,
      skipped: 0,
      courses: [
        { id: 1, name: "Triathlon S", event_type: "triathlon-s" },
        { id: 2, name: "Triathlon M", event_type: "triathlon-m" },
        { id: 3, name: "Triathlon L", event_type: "triathlon-l" },
      ],
    });
    renderForm();
    // Le titre du sélecteur annonce le nombre de courses (compteur unique — le
    // reste du texte est en fragments donc pas testé littéralement).
    expect(screen.getByText(/3 courses importées/)).toBeInTheDocument();
    // Le bouton file vers la première course par défaut, sans interaction.
    const link = screen.getByRole("link", { name: /Voir les résultats/ });
    expect(link.getAttribute("href")).toBe("/courses/1");
  });

  it("multi : sélectionner une autre course met à jour la cible du bouton", async () => {
    importMock.set({
      phase: "done",
      imported: 300,
      skipped: 0,
      courses: [
        { id: 1, name: "Triathlon S", event_type: "triathlon-s" },
        { id: 2, name: "Triathlon M", event_type: "triathlon-m" },
      ],
    });
    renderForm();
    // Le sélecteur est un `<select>` natif restylé (label accessible via aria-label).
    const select = screen.getByRole("combobox", { name: /Choisir la course/ });
    await userEvent.selectOptions(select, "2");
    expect(
      screen.getByRole("link", { name: /Voir les résultats/ }).getAttribute("href"),
    ).toBe("/courses/2");
  });

  it("propose aussi la navigation sur le doublon (résultats déjà en base)", () => {
    // Chemin cache TTL frais : imported=0, skipped>0, cached=true.
    importMock.set({
      phase: "done",
      cached: true,
      imported: 0,
      skipped: 250,
      courses: [
        { id: 7, name: "Duathlon de La Baule 2026", event_type: "duathlon-s" },
      ],
    });
    renderForm();
    // L'alerte doublon (title « Résultats déjà enregistrés ») doit exister ET
    // porter le lien : c'est le point de l'issue #135 pour ce cas.
    expect(screen.getByText(/Résultats déjà enregistrés/)).toBeInTheDocument();
    const link = screen.getByRole("link", {
      name: /Voir les résultats de « Duathlon de La Baule 2026 »/,
    });
    expect(link.getAttribute("href")).toBe("/courses/7");
  });

  it("ne rend rien si le backend n'a remonté aucune course (import vide)", () => {
    importMock.set({
      phase: "done",
      imported: 0,
      skipped: 0,
      courses: [],
    });
    renderForm();
    expect(screen.queryByRole("link", { name: /Voir les résultats/ })).not.toBeInTheDocument();
  });
});

describe("TcnScrapeForm — rafraîchissement de la liste après import (#201)", () => {
  it("appelle router.refresh() quand le SSE émet phase=done avec un import réel", () => {
    importMock.set({
      phase: "done",
      cached: false,
      imported: 12,
      skipped: 0,
      courses: [{ id: 42, name: "Triathlon de Nantes 2026", event_type: "triathlon-m" }],
    });
    renderForm();
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("n'appelle pas router.refresh() sur un doublon (cache TTL frais)", () => {
    importMock.set({
      phase: "done",
      cached: true,
      imported: 0,
      skipped: 250,
      courses: [{ id: 7, name: "Duathlon de La Baule 2026", event_type: "duathlon-s" }],
    });
    renderForm();
    expect(refreshMock).not.toHaveBeenCalled();
  });

  it("n'appelle pas router.refresh() tant que la phase n'est pas `done`", () => {
    importMock.set({
      phase: "scraping",
      imported: 0,
      skipped: 0,
      courses: [],
    });
    renderForm();
    expect(refreshMock).not.toHaveBeenCalled();
  });
});
