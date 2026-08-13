import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation } from "@/lib/types";

const getParticipation = vi.fn();
const notFound = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: { getParticipation: (id: number) => getParticipation(id) },
}));

// Le vrai `notFound()` interrompt le rendu en levant : un mock qui se contente
// d'enregistrer l'appel laisserait le composant continuer sur des données
// absentes et testerait un chemin qui n'existe pas en production.
vi.mock("next/navigation", () => ({
  notFound: () => {
    notFound();
    throw new Error("NEXT_HTTP_ERROR_FALLBACK;404");
  },
}));

import ParticipationDetailPage from "./page";

const ATHLETE = { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" };

function participation(over: Partial<Participation> = {}): Participation {
  return {
    id: 42,
    athlete: ATHLETE,
    course: {
      id: 3,
      name: "Triathlon de Nantes",
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "raceresult",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: "V1H",
    bib_number: "56",
    rank_overall: 56,
    rank_category: 4,
    rank_gender: 41,
    total_time: "02:02:31",
    status: "finisher",
    is_relay: false,
    splits: { swim: "00:22:52", bike: "01:01:07", run: "00:33:45" },
    created_at: null,
    stats: null,
    ...over,
  };
}

async function renderPage(row: Participation | null, courseId = "3") {
  if (row === null) getParticipation.mockRejectedValue(new Error("404"));
  else getParticipation.mockResolvedValue(row);
  const ui = await ParticipationDetailPage({
    params: Promise.resolve({ id: courseId, participationId: "42" }),
  });
  return render(ui);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ParticipationDetailPage", () => {
  it("rend l'état « statistiques indisponibles » quand stats est null", async () => {
    await renderPage(participation({ stats: null }));

    expect(screen.getByText(/statistiques indisponibles/i)).toBeTruthy();
    expect(screen.getByText(/intégralité des résultats/i)).toBeTruthy();
  });

  it("propose un retour vers les résultats de l'athlète depuis l'état indisponible", async () => {
    await renderPage(participation({ stats: null }));

    const retour = screen.getByRole("link", { name: /résultats de l'athlète/i });
    expect(retour.getAttribute("href")).toBe("/athletes/7");
  });

  it("n'affiche aucun tableau ni graphique quand les statistiques sont indisponibles", async () => {
    const { container } = await renderPage(participation({ stats: null }));

    expect(screen.queryByRole("table")).toBeNull();
    expect(container.querySelector("svg")).toBeNull();
  });

  it("traite comme introuvable une participation qui n'appartient pas à la course de l'URL", async () => {
    await expect(renderPage(participation({ stats: null }), "999")).rejects.toThrow();

    expect(notFound).toHaveBeenCalled();
  });

  it("traite comme introuvable une participation inexistante", async () => {
    await expect(renderPage(null)).rejects.toThrow();

    expect(notFound).toHaveBeenCalled();
  });
});
