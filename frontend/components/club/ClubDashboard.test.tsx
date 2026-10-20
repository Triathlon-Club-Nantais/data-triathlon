import { describe, it, expect, vi } from "vitest";
import { render as renderRTL, screen, type RenderResult } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import type { ClubSummary, Participation, Stats } from "@/lib/types";

vi.mock("@/components/charts/BarList", () => ({ BarList: () => <div data-testid="barlist" /> }));
vi.mock("@/components/charts/MonthlyTrend", () => ({ MonthlyTrend: () => <div data-testid="monthly" /> }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/club",
}));
const { session } = vi.hoisted(() => ({ session: { permissions: ["pages:preview"] as string[] } }));
vi.mock("@/lib/queries/auth", () => ({
  useSession: () => ({ data: session }),
  useHydratedSession: () => ({ data: session }),
}));

import { ClubDashboard } from "./ClubDashboard";
import { currentSeason, seasonAbsenceLabel, seasonLabel, seasonSelectionLabel } from "@/lib/utils/season";

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
  podiums_totals: { scratch: 0, category: 0, gender: 0, all: 0 },
  podiums_by_discipline: {},
  composition: { gender: {}, category: {} },
  licensees: null,
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
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
    expect(screen.getByText("Résultats")).toBeInTheDocument();
    expect(screen.getByText("Athlètes")).toBeInTheDocument();
    expect(screen.getByText("Épreuves")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("the four KPI read the same stats and Résultats hints the selection", () => {
    render(
      <ClubDashboard
        stats={{ ...STATS, total: 42, athletes: 9, events: 4 }}
        summary={EMPTY_SUMMARY}
        recent={[part({ id: 1 })]}
        seasons={[2024, 2025]}
      />,
    );
    const value = (label: string) =>
      screen.getByText(label).parentElement!.parentElement!.querySelector(".tcn-stat-value");
    expect(value("Résultats")).toHaveTextContent("42");
    expect(value("Athlètes")).toHaveTextContent("9");
    expect(value("Épreuves")).toHaveTextContent("4");
    const hints = screen.getAllByTestId("statcard-hint");
    expect(hints).toHaveLength(1);
    expect(hints[0]).toHaveTextContent(seasonSelectionLabel([2024, 2025]));
  });

  it("les liens vers les listes gardent la sélection de saisons", () => {
    render(
      <ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} seasons={[2024, 2025]} />,
    );
    expect(screen.getByRole("link", { name: /Tout voir/ })).toHaveAttribute(
      "href",
      "/resultats?scope=club&seasons=2024,2025",
    );
    expect(screen.getByRole("link", { name: /Voir saison par saison/ })).toHaveAttribute(
      "href",
      "/club/athletes?seasons=2024,2025",
    );
  });

  it("empty state quand aucun résultat", () => {
    render(
      <ClubDashboard
        stats={{ ...STATS, total: 0 }}
        summary={EMPTY_SUMMARY}
        recent={[]}
        seasons={[currentSeason()]}
      />,
    );
    expect(screen.getByText(/Aucun résultat enregistré pour la saison/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Voir la saison en cours" })).toBeNull();
    const ajouter = screen.getByRole("link", { name: "Ajouter une épreuve" });
    expect(ajouter).toHaveAttribute("href", "/ajouter");
    expect(ajouter).toHaveClass("tcn-cible-tactile");
  });

  it("roster : décompose les podiums d'un athlète par scope, avec tooltip", () => {
    const summary: ClubSummary = {
      ...EMPTY_SUMMARY,
      roster: [{
        athlete_id: 1, prenom: "P", nom: "N", count: 3,
        podiums: 1, podiums_overall: 1, podiums_gender: 1, podiums_category: 1,
      }],
    };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
    expect(screen.getByLabelText("1 podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de genre")).toBeInTheDocument();
  });

  it("roster : aucun badge scope pour un athlète sans podium", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 0)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
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
        seasons={[currentSeason()]}
      />,
    );

    const section = screen
      .getByRole("heading", { name: "Les athlètes les plus actifs" })
      .closest("section");
    expect(section?.querySelectorAll('a[href^="/athletes/"]')).toHaveLength(APERCU_ROSTER);
    expect(screen.getByRole("link", { name: "Voir saison par saison →" })).toHaveAttribute(
      "href",
      `/club/athletes?seasons=${currentSeason()}`,
    );
  });

  it("roster : aucun lien vers /club/athletes sans le pouvoir pages:preview (#925)", () => {
    session.permissions = [];
    try {
      const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1)] };
      const { container } = render(
        <ClubDashboard stats={STATS} summary={summary} recent={[]} seasons={[currentSeason()]} />,
      );

      expect(screen.queryByText("Voir saison par saison →")).not.toBeInTheDocument();
      expect(container.querySelector('a[href^="/club/athletes"]')).toBeNull();
    } finally {
      session.permissions = ["pages:preview"];
    }
  });

  it("roster : titre « Athlètes du club » sous le plafond", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
    expect(screen.getByRole("heading", { name: "Athlètes du club" })).toBeInTheDocument();
  });

  it("nomme la portée des podiums du roster en légende (PROF-3, #488)", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 1)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
    expect(
      screen.getByText("Les podiums comptés ici cumulent le général, le genre et la catégorie, hors relais."),
    ).toBeInTheDocument();
  });

  it("n'affiche pas la légende des podiums quand aucun athlète de l'aperçu n'en a", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 0)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
    expect(
      screen.queryByText("Les podiums comptés ici cumulent le général, le genre et la catégorie, hors relais."),
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
    render(<ClubDashboard stats={STATS} summary={summary} recent={[]} seasons={[currentSeason()]} />);

    const onglet = screen.getByRole("tab", { name: "Composition" });
    expect(onglet).toBeInTheDocument();
    await userEvent.click(onglet);

    // Les deux sections sont repliées par défaut (#653) : leur contenu
    // n'apparaît qu'une fois dépliées.
    const declencheurGenre = await screen.findByRole("button", { name: "Par genre" });
    const declencheurCategorie = screen.getByRole("button", { name: "Par catégorie" });
    expect(declencheurGenre).toHaveAttribute("aria-expanded", "false");
    expect(declencheurCategorie).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(declencheurGenre);
    await userEvent.click(declencheurCategorie);

    expect(screen.getAllByTestId("barlist")).toHaveLength(2);
  });

  it("résultats récents : rend `recent` directement, sans re-tri", () => {
    const recent = [part({ id: 5 }), part({ id: 9 })];
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={recent} seasons={[currentSeason()]} />);
    expect(screen.getAllByRole("link", { name: /Course \d/ })).toHaveLength(2);
  });

  // #1441 : part des licenciés de la saison qui ont couru au moins une fois.
  it("affiche le KPI Licenciés en course : ceux qui ont couru, sur le total de la saison", () => {
    render(
      <ClubDashboard
        stats={STATS}
        summary={{ ...EMPTY_SUMMARY, licensees: { season: 2026, total: 182, raced: 97 } }}
        recent={[part({ id: 1 })]}
        seasons={[currentSeason()]}
      />,
    );
    const carte = screen.getByText("Licenciés en course").parentElement!.parentElement!;
    expect(carte.querySelector(".tcn-stat-value")).toHaveTextContent(/^97$/);
    expect(carte).toHaveTextContent(`sur 182 licenciés · ${seasonLabel(2026)}`);
  });

  it("masque le KPI Licenciés en course sans licencié pour la saison", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
    expect(screen.queryByText("Licenciés en course")).not.toBeInTheDocument();
  });

  // #581 : le bandeau de troncature disparaît — roster et podiums sont exacts,
  // il n'y a plus de plafond à annoncer.
  it("ne rend plus de bandeau de troncature", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} seasons={[currentSeason()]} />);
    expect(screen.queryByText(/derniers résultats importés/)).not.toBeInTheDocument();
  });

  it("hides the composition card under a gender filter", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[]} seasons={[currentSeason()]} gender="F" />);

    expect(screen.queryByRole("tab", { name: "Composition" })).not.toBeInTheDocument();
  });

  it("falls back to the default tab when Composition is open and a gender is picked", async () => {
    const props = { stats: STATS, summary: EMPTY_SUMMARY, recent: [], seasons: [currentSeason()] };
    const { rerender } = render(<ClubDashboard {...props} />);
    await userEvent.click(screen.getByRole("tab", { name: "Composition" }));

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ClubDashboard {...props} gender="F" />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("tab", { name: "Par discipline" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("barlist")).toBeVisible();
  });

  it("keeps the open tab when the sex filter changes", async () => {
    const props = { stats: STATS, summary: EMPTY_SUMMARY, recent: [], seasons: [currentSeason()] };
    const wrap = (gender?: "F" | "M") => (
      <QueryClientProvider client={new QueryClient()}>
        <ClubDashboard {...props} gender={gender} />
      </QueryClientProvider>
    );
    const { rerender } = render(<ClubDashboard {...props} />);
    await userEvent.click(screen.getByRole("tab", { name: "Performance" }));

    rerender(wrap("M"));
    expect(screen.getByRole("tab", { name: "Performance" })).toHaveAttribute("aria-selected", "true");

    rerender(wrap("F"));
    expect(screen.getByRole("tab", { name: "Performance" })).toHaveAttribute("aria-selected", "true");
  });

  it("names the sex and offers to drop it when the filter leaves no result", () => {
    render(
      <ClubDashboard stats={{ ...STATS, total: 0 }} summary={EMPTY_SUMMARY} recent={[]} seasons={[2025]} gender="F" />,
    );

    expect(screen.getByText(`Aucun résultat enregistré chez les femmes pour ${seasonAbsenceLabel([2025])}.`)).toBeInTheDocument();
    expect(screen.queryByText(/Aucun résultat enregistré pour/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Retirer le filtre par sexe" })).toHaveAttribute("href", "/club");
  });

  it("keeps the sexe in the link to the season list", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[]} seasons={[2025]} gender="M" />);

    expect(screen.getByRole("link", { name: /saison par saison/ })).toHaveAttribute(
      "href",
      "/club/athletes?seasons=2025&sexe=H",
    );
  });
});
