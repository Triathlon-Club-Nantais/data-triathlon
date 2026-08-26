import { describe, it, expect, vi } from "vitest";
import { render as renderRTL, screen, type RenderResult } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import type { ClubSummary, Participation, Stats } from "@/lib/types";

vi.mock("@/components/charts/BarList", () => ({ BarList: () => <div data-testid="barlist" /> }));
vi.mock("@/components/charts/MonthlyTrend", () => ({ MonthlyTrend: () => <div data-testid="monthly" /> }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));

import { ClubDashboard } from "./ClubDashboard";

// `RosterApercu` appelle `useClubRosterRank` (#641), inconditionnellement
// (l'`enabled` du hook ne change rien à l'obligation d'un `QueryClientProvider`
// ancêtre) — il doit donc envelopper tout rendu de `ClubDashboard`.
function render(ui: ReactElement): RenderResult {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderRTL(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const APERCU_ROSTER = 12;

const STATS: Stats = {
  total: 1,
  athletes: 1,
  events: 1,
  by_type: {},
  by_month: {},
  recent: [],
  rank_counters: {
    scratch: { victories: 0, podiums: 0, top10: 0 },
    category: { victories: 0, podiums: 0, top10: 0 },
    all: { victories: 0, podiums: 0, top10: 0 },
    gender: { women: { victories: 0, podiums: 0, top10: 0 }, men: { victories: 0, podiums: 0, top10: 0 } },
  },
};

const EMPTY_SUMMARY: ClubSummary = {
  roster: [],
  podiums: { scratch: [], category: [], gender: [], all: [] },
  podiums_by_discipline: {},
  composition: { gender: {}, category: {} },
};

function rosterEntry(i: number, podiums = 0) {
  return {
    athlete_id: i,
    prenom: "P",
    nom: `N${i}`,
    count: 10 - i,
    podiums,
    podiums_overall: podiums,
    podiums_gender: 0,
    podiums_category: 0,
  };
}

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id, name: `Course ${over.id}`, event_date: "2026-05-10",
      event_type: "triathlon-m", provider: "manuel", source_url: "", is_relay: false,
    },
    club: "TCN", is_tcn: true, category: null, bib_number: null,
    rank_overall: over.rank_overall ?? null, rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null, total_time: "01:59:00", status: "finisher",
    is_relay: false, splits: null, created_at: "2026-05-11T10:00:00Z",
  };
}

describe("ClubDashboard — smoke", () => {
  it("rend les 4 KPI de synthèse", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} />);
    expect(screen.getByText("Résultats")).toBeInTheDocument();
    expect(screen.getByText("Athlètes")).toBeInTheDocument();
    expect(screen.getByText("Épreuves")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("empty state quand aucun résultat", () => {
    render(
      <ClubDashboard
        stats={{ ...STATS, total: 0 }}
        summary={EMPTY_SUMMARY}
        recent={[]}
      />,
    );
    expect(screen.getByText("Aucun résultat de club")).toBeInTheDocument();
  });

  it("roster : décompose les podiums d'un athlète par scope, avec tooltip", () => {
    const summary: ClubSummary = {
      ...EMPTY_SUMMARY,
      roster: [{
        athlete_id: 1, prenom: "P", nom: "N", count: 3,
        podiums: 1, podiums_overall: 1, podiums_gender: 1, podiums_category: 1,
      }],
    };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(screen.getByLabelText("1 podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de genre")).toBeInTheDocument();
  });

  it("roster : aucun badge scope pour un athlète sans podium", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 0)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(screen.queryByLabelText(/podium général/)).not.toBeInTheDocument();
  });

  // Le roster arrive déjà plafonné à 12 côté backend (#581, club_roster) :
  // ClubDashboard ne tronque plus rien, il rend `summary.roster` tel quel.
  it("roster : rend tel quel et renvoie vers /club/athletes", () => {
    const summary: ClubSummary = {
      ...EMPTY_SUMMARY,
      roster: Array.from({ length: APERCU_ROSTER }, (_, i) => rosterEntry(i + 1)),
    };
    render(
      <ClubDashboard
        stats={{ ...STATS, athletes: 20 }}
        summary={summary}
        recent={[part({ id: 1 })]}
      />,
    );

    const section = screen
      .getByRole("heading", { name: "Les athlètes les plus actifs" })
      .closest("section");
    expect(section?.querySelectorAll('a[href^="/athletes/"]')).toHaveLength(APERCU_ROSTER);
    expect(screen.getByRole("link", { name: "Voir saison par saison →" })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
  });

  it("roster : titre « Athlètes du club » sous le plafond", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(screen.getByRole("heading", { name: "Athlètes du club" })).toBeInTheDocument();
  });

  it("nomme la portée des podiums du roster en légende (PROF-3, #488)", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 1)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(
      screen.getByText("Les podiums comptés ici cumulent le général, le genre et la catégorie."),
    ).toBeInTheDocument();
  });

  it("n'affiche pas la légende des podiums quand aucun athlète de l'aperçu n'en a", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 0)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(
      screen.queryByText("Les podiums comptés ici cumulent le général, le genre et la catégorie."),
    ).not.toBeInTheDocument();
  });

  // US9 (#466) : la composition du club (genre, catégorie), agrégée côté
  // serveur (#642, `ClubSummary.composition`) — `/club` la transporte déjà,
  // affichée dans son propre onglet.
  it("affiche la composition du club (genre et catégorie) dans son propre onglet", async () => {
    const summary: ClubSummary = {
      ...EMPTY_SUMMARY,
      composition: { gender: { F: 1, M: 1 }, category: { S3: 1, S4: 1 } },
    };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[]} />);

    const onglet = screen.getByRole("tab", { name: "Composition" });
    expect(onglet).toBeInTheDocument();
    await userEvent.click(onglet);

    expect(await screen.findByText("Par genre")).toBeInTheDocument();
    expect(screen.getByText("Par catégorie")).toBeInTheDocument();
    expect(screen.getAllByTestId("barlist")).toHaveLength(2);
  });

  it("résultats récents : rend `recent` directement, sans re-tri", () => {
    const recent = [part({ id: 5 }), part({ id: 9 })];
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={recent} />);
    expect(screen.getAllByRole("link", { name: /Course \d/ })).toHaveLength(2);
  });

  // #581 : le bandeau de troncature disparaît — roster et podiums sont exacts,
  // il n'y a plus de plafond à annoncer.
  it("ne rend plus de bandeau de troncature", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} />);
    expect(screen.queryByText(/derniers résultats importés/)).not.toBeInTheDocument();
  });
});
