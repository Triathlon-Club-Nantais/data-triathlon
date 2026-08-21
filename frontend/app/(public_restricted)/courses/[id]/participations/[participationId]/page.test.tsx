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

const STATS = {
  segments: ["swim", "bike", "run"],
  ranking_evolution: [
    { segment: "swim", scratch_position: 61, segment_position: 58 },
    { segment: "bike", scratch_position: 58, segment_position: 44 },
    { segment: "run", scratch_position: 56, segment_position: 63 },
  ],
  comparison: [{ position_label: "1er", rank: 1, percentages: { swim: 141.6, total: 128.0 } }],
  improvement: [{ segment: "bike", gains: { "0.5": 1, "1": 2, "2": 3, "5": 7, "10": 12, "25": 25 } }],
};

describe("ParticipationDetailPage", () => {
  it("propose un retour vers la course et vers les résultats de l'athlète", async () => {
    await renderPage(participation({ stats: STATS }));

    expect(screen.getByRole("link", { name: /retour à la course/i }).getAttribute("href")).toBe(
      "/courses/3",
    );
    expect(
      screen.getByRole("link", { name: /retour aux résultats de l'athlète/i }).getAttribute("href"),
    ).toBe("/athletes/7");
  });

  it("ouvre la page de la course depuis son nom", async () => {
    await renderPage(participation({ stats: STATS }));

    const titre = screen.getByRole("link", { name: "Triathlon de Nantes" });
    expect(titre.getAttribute("href")).toBe("/courses/3");
  });

  it("n'affiche pas d'action d'ajout de triathlon sur une page de résultat", async () => {
    await renderPage(participation({ stats: STATS }));

    expect(screen.queryByRole("link", { name: /ajouter un triathlon/i })).toBeNull();
  });

  it("garde les deux retours quand les statistiques sont indisponibles", async () => {
    await renderPage(participation({ stats: null }));

    expect(screen.getByRole("link", { name: /retour à la course/i }).getAttribute("href")).toBe(
      "/courses/3",
    );
  });

  it("rend l'état « comparaison indisponible » quand stats est null", async () => {
    await renderPage(participation({ stats: null }));

    expect(screen.getByText(/comparaison au classement indisponible/i)).toBeTruthy();
    expect(screen.getByText(/intégralité des résultats/i)).toBeTruthy();
  });

  it("affiche le résultat de l'athlète même quand les statistiques sont indisponibles (#462)", async () => {
    await renderPage(participation({ stats: null }));

    expect(screen.getByText("DUPONT Jean")).toBeTruthy();
    expect(screen.getByText("02:02:31")).toBeTruthy();
    expect(screen.getByText("56")).toBeTruthy();
  });

  it("ne garde qu'un seul niveau de titre h1 quand les statistiques sont indisponibles", async () => {
    await renderPage(participation({ stats: null }));

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("propose un retour vers les résultats de l'athlète depuis l'état indisponible", async () => {
    await renderPage(participation({ stats: null }));

    const retour = screen.getByRole("link", { name: /résultats de l'athlète/i });
    expect(retour.getAttribute("href")).toBe("/athletes/7");
  });

  it("n'affiche aucun tableau ni graphique quand les statistiques sont indisponibles", async () => {
    await renderPage(participation({ stats: null }));

    expect(screen.queryByRole("table")).toBeNull();
    // Le graphique porte un rôle explicite ; les seuls SVG restants sont les
    // chevrons décoratifs des liens de retour.
    expect(screen.queryByRole("img", { name: /évolution de la position/i })).toBeNull();
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
