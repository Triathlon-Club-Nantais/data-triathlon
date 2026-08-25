import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation, Stats } from "@/lib/types";

// Charts et hooks Next.js : stubs neutres.
vi.mock("@/components/charts/BarList", () => ({
  BarList: () => <div data-testid="barlist" />,
}));
vi.mock("@/components/charts/MonthlyTrend", () => ({
  MonthlyTrend: () => <div data-testid="monthly" />,
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

import { ClubDashboard, APERCU_ROSTER } from "./ClubDashboard";
import { CLUB_PARTICIPATIONS_PAGE_SIZE } from "@/lib/club";

const STATS: Stats = {
  total: 0,
  athletes: 0,
  events: 0,
  by_type: {},
  by_month: {},
  recent: [],
  rank_counters: {
    scratch: { victories: 0, podiums: 0, top10: 0 },
    category: { victories: 0, podiums: 0, top10: 0 },
    all: { victories: 0, podiums: 0, top10: 0 },
    gender: {
      women: { victories: 0, podiums: 0, top10: 0 },
      men: { victories: 0, podiums: 0, top10: 0 },
    },
  },
};

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id,
      name: `Course ${over.id}`,
      event_date: "2026-05-10",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null,
    total_time: "01:59:00",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: "2026-05-11T10:00:00Z",
  };
}

const PARTS: Participation[] = [part({ id: 1, rank_overall: 2 })];

// Le filtrage détaillé par mode vit désormais dans PodiumsList.test.tsx : ce
// composant client lit `?rank=…` et recalcule localement (issue #132).
// Ce test se limite au smoke : la section podiums est bien montée et affiche
// les KPI de synthèse.
describe("ClubDashboard — smoke", () => {
  it("rend les 4 KPI de synthèse (Résultats / Athlètes / Épreuves / Podiums)", () => {
    render(
      <ClubDashboard
        stats={STATS}
        participations={[part({ id: 1, rank_overall: 2 })]}
      />,
    );
    expect(screen.getByText("Résultats")).toBeInTheDocument();
    expect(screen.getByText("Athlètes")).toBeInTheDocument();
    expect(screen.getByText("Épreuves")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("empty state quand aucune participation", () => {
    render(<ClubDashboard stats={STATS} participations={[]} />);
    expect(screen.getByText("Aucun résultat de club")).toBeInTheDocument();
  });

  // Roster (issue #128, extension) : le décompte de podiums d'un athlète se
  // décompose par scope (général / catégorie / genre) avec l'icône et le
  // tooltip natif du composant PodiumsList — un athlète 1er scratch et 1er
  // catégorie n'agrège plus en « 2 podiums » sans nuance.
  it("roster : décompose les podiums d'un athlète par scope, avec tooltip", () => {
    const parts: Participation[] = [
      // Ath 1 : podium général x1
      part({ id: 1, rank_overall: 2 }),
      // Ath 1 (même id) : podium catégorie x1 sur une autre course
      part({
        id: 2,
        athlete: { id: 1, nom: "N", prenom: "P", gender: "F", club: "TCN" },
        rank_overall: 30,
        rank_category: 1,
      }),
      // Ath 1 : podium genre x1 sur une troisième course
      part({
        id: 3,
        athlete: { id: 1, nom: "N", prenom: "P", gender: "F", club: "TCN" },
        rank_gender: 3,
      }),
    ];
    render(<ClubDashboard stats={STATS} participations={parts} />);
    expect(screen.getByLabelText("1 podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de genre")).toBeInTheDocument();
  });

  // Cas mesuré (Hadrien à Mesquer, athlète 8565) : une seule participation
  // podium sur les trois dimensions à la fois — 2e scratch, 1er catégorie,
  // 2e genre. Les trois compteurs de scope sont incrémentés indépendamment.
  it("roster : une participation podium sur plusieurs scopes incrémente chaque compteur", () => {
    const parts: Participation[] = [
      part({ id: 1, rank_overall: 2, rank_category: 1, rank_gender: 2 }),
    ];
    render(<ClubDashboard stats={STATS} participations={parts} />);
    expect(screen.getByLabelText("1 podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de genre")).toBeInTheDocument();
  });

  it("roster : aucun badge scope pour un athlète sans podium", () => {
    const parts: Participation[] = [
      part({
        id: 10,
        athlete: { id: 10, nom: "Z", prenom: "Q", gender: "M", club: "TCN" },
        rank_overall: 50,
      }),
    ];
    render(<ClubDashboard stats={STATS} participations={parts} />);
    expect(screen.queryByLabelText(/podium général/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/podium de catégorie/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/podium de genre/)).not.toBeInTheDocument();
  });

  // PROF-2 (#487) : le roster rendait les 350 athlètes du club, soit
  // 1,69 Mo de document et 362 liens, triés par volume — qui cherche un nom
  // traversait 164 fiches à « 1 course ». Il devient un aperçu, la recherche
  // et le tri vivant déjà sur /club/athletes.
  it("roster : n'affiche qu'un aperçu et renvoie vers /club/athletes", () => {
    const parts = Array.from({ length: APERCU_ROSTER + 8 }, (_, i) =>
      part({
        id: i + 1,
        athlete: { id: i + 1, nom: `N${i}`, prenom: "P", gender: "F", club: "TCN" },
      }),
    );
    render(<ClubDashboard stats={STATS} participations={parts} />);

    // Le titre dit **ce qui est montré** : `buildRoster` trie par volume
    // décroissant, donc l'aperçu est le peloton de tête, pas un échantillon.
    // Scopé à la section : `ResultCard` lie lui aussi vers /athletes/.
    const section = screen
      .getByRole("heading", { name: "Les athlètes les plus actifs" })
      .closest("section");
    expect(section?.querySelectorAll('a[href^="/athletes/"]')).toHaveLength(APERCU_ROSTER);

    // Le libellé dit la destination, pas un décompte : /club/athletes s'ouvre
    // sur la saison en cours seule, quand `roster.length` agrège toutes les
    // saisons. Le total du club vit dans le KPI « Athlètes ».
    expect(screen.getByRole("link", { name: "Voir saison par saison →" })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
  });

  it("roster : pas de renvoi « voir tous » quand l'aperçu suffit", () => {
    render(<ClubDashboard stats={STATS} participations={[part({ id: 1 })]} />);
    // Le renvoi est inconditionnel : « les deux écrans reliés dans les deux
    // sens » est une garantie de navigation, elle ne peut pas dépendre du
    // volume de données. Seul le titre bascule.
    expect(screen.getByRole("link", { name: "Voir saison par saison →" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Athlètes du club" })).toBeInTheDocument();
  });

  // Le plafond de `page_size` se lit sur la longueur reçue : à ras bord, la
  // page tronque en silence — les 4 KPI compris. On le dit plutôt que de
  // laisser croire à une synthèse complète.
  it("dit le plafond quand la page arrive pleine", () => {
    const parts = Array.from({ length: CLUB_PARTICIPATIONS_PAGE_SIZE }, (_, i) =>
      part({
        id: i + 1,
        athlete: { id: i + 1, nom: `N${i}`, prenom: "P", gender: "F", club: "TCN" },
      }),
    );
    render(<ClubDashboard stats={STATS} participations={parts} />);
    // `list_participations` trie par `created_at desc` (date d'**import**),
    // pas par date d'épreuve : la note ne doit pas promettre un ordre
    // chronologique que le backend ne rend pas.
    expect(screen.getByText(/derniers résultats importés/)).toBeInTheDocument();
  });

  it("ne dit rien du plafond sous le plafond", () => {
    render(<ClubDashboard stats={STATS} participations={[part({ id: 1 })]} />);
    expect(screen.queryByText(/derniers résultats importés/)).not.toBeInTheDocument();
  });

  // #488 (PROF-3) : les podiums du roster cumulent les trois portées sans
  // condition, quand le KPI plus haut suit `?rank=`. Le dire est ce qui
  // manquait — aucun chiffre ne change.
  it("nomme la portée des podiums du roster en légende des cartes (PROF-3, #488)", () => {
    render(<ClubDashboard stats={STATS} participations={PARTS} />);

    expect(
      screen.getByText("Les podiums comptés ici cumulent le général, le genre et la catégorie."),
    ).toBeInTheDocument();
  });

  // Revue finale (#488) : la légende qualifiait des nombres absents de
  // l'écran sur un club sans aucun podium — les cartes ne rendent leur
  // décompte que sous condition (`r.podiums > 0`).
  it("n'affiche pas la légende des podiums quand aucun athlète de l'aperçu n'en a", () => {
    render(
      <ClubDashboard
        stats={STATS}
        participations={[part({ id: 1, rank_overall: 50 })]}
      />,
    );

    expect(
      screen.queryByText("Les podiums comptés ici cumulent le général, le genre et la catégorie."),
    ).not.toBeInTheDocument();
  });
});
