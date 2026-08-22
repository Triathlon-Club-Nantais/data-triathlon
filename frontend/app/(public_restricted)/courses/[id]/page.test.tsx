import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { CourseSource, CourseSummary } from "@/lib/types";
import { ApiError } from "@/lib/api/client";

const getCourse = vi.fn();
const getCourseSummary = vi.fn();
const getCourseSources = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getCourse: (id: number, opts: unknown) => getCourse(id, opts),
    getCourseSummary: (id: number) => getCourseSummary(id),
    getCourseSources: (id: number) => getCourseSources(id),
  },
}));

// RaceFinishers est un composant client.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/courses/1",
  useSearchParams: () => new URLSearchParams(),
  notFound: () => {
    throw new Error("notFound");
  },
}));

// `CourseSourcesPanel` est testé pour lui-même dans son propre fichier
// (permissions, bascule, confirmation), avec un vrai `QueryClientProvider`.
// Ici, un visiteur anonyme systématique et une mutation neutre suffisent à
// vérifier que la page affiche bien la liste de sources reçue.
vi.mock("@/lib/queries/auth", () => ({
  useSession: () => ({ data: null }),
}));
vi.mock("@/lib/queries/admin", () => ({
  useSwitchCourseSource: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import CoursePage from "./page";

const COURSE = {
  id: 1,
  name: "Triathlon de Nantes",
  event_date: "2026-05-16",
  event_type: "triathlon-m",
  provider: "klikego",
  source_url: "https://exemple.fr/x",
  is_relay: false,
};

const SUMMARY: CourseSummary = {
  total: 1811,
  finishers: 1768,
  non_finishers: 43,
  dnf: 43,
  dns: 0,
  dsq: 0,
  unknown: 0,
  tcn_count: 4,
  male: 1063,
  female: 747,
  categories: [
    { name: "S2", count: 284 },
    { name: "S3", count: 216 },
  ],
  // Volontairement supérieur à la somme des deux rendues : c'est tout l'objet
  // du champ, et le test du pourcentage ci-dessous en dépend.
  categories_total: 1000,
  clubs: [
    { name: "GRAVELINES TRIATHLON", count: 51, is_tcn: false },
    { name: "TRIATHLON CLUB NANTAIS", count: 4, is_tcn: true },
  ],
  histogram: { bars: [3, 18, 47], start_sec: 3600, bucket_sec: 300 },
  split_keys: [],
};

const ONE_SOURCE: CourseSource[] = [
  { id: 1, url: "https://exemple.fr/x", provider: "klikego", is_active: true, last_scraped_at: null },
];

beforeEach(() => {
  vi.clearAllMocks();
  getCourse.mockResolvedValue({
    course: COURSE,
    participations: [],
    total: 1811,
    page: 1,
    page_size: 20,
  });
  getCourseSummary.mockResolvedValue(SUMMARY);
  getCourseSources.mockResolvedValue(ONE_SOURCE);
});

async function afficher(searchParams: Record<string, string | undefined> = {}) {
  const ui = await CoursePage({
    params: Promise.resolve({ id: "1" }),
    searchParams: Promise.resolve(searchParams),
  });
  return render(ui);
}

describe("CoursePage", () => {
  it("rend le nom de l'épreuve en <h1> et les titres de carte en <h2> (A11Y-2)", async () => {
    await afficher();

    expect(screen.getByRole("heading", { level: 1, name: "Triathlon de Nantes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Répartition genre" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Répartition par catégorie" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Top clubs" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Distribution des temps des finishers" }),
    ).toBeInTheDocument();
  });

  it("écrit le club TCN du classement « Top clubs » en `--tcn-orange-deeper`, seul token à tenir 4,5:1 (A11Y-4)", async () => {
    await afficher();

    const nom = screen.getByText("TRIATHLON CLUB NANTAIS");
    const compte = nom.nextElementSibling as HTMLElement;
    expect(nom.style.color).toBe("var(--tcn-orange-deeper)");
    expect(compte).toHaveTextContent("4");
    expect(compte.style.color).toBe("var(--tcn-orange-deeper)");
  });

  it("alimente les six blocs depuis la synthèse, pas depuis les lignes affichées", async () => {
    // Aucune participation dans la charge : tout ce qui suit vient de la synthèse.
    await afficher();

    expect(screen.getByText("1811")).toBeInTheDocument(); // participants
    expect(screen.getByText("1768")).toBeInTheDocument(); // finishers
    expect(screen.getByText("43")).toBeInTheDocument(); // abandons
    expect(screen.getByText(/4 athlètes TCN/)).toBeInTheDocument();
    expect(screen.getByText("59%")).toBeInTheDocument(); // 1063 / 1810 hommes
    expect(screen.getByText("S2")).toBeInTheDocument();
    expect(screen.getByText("GRAVELINES TRIATHLON")).toBeInTheDocument();
    expect(screen.getByText(/Distribution des temps/)).toBeInTheDocument();
  });

  it("distingue abandons, non-partants et disqualifiés plutôt que de les agréger (#331)", async () => {
    getCourseSummary.mockResolvedValue({ ...SUMMARY, non_finishers: 8, dnf: 5, dns: 2, dsq: 1 });

    await afficher();

    expect(screen.getByText("Abandons")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Non-partants")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Disqualifiés")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("n'affiche aucune pastille vide pour les non-partants ni les disqualifiés (#331)", async () => {
    // SUMMARY : dnf=43, dns=0, dsq=0.
    await afficher();

    expect(screen.getByText("Abandons")).toBeInTheDocument();
    expect(screen.queryByText("Non-partants")).not.toBeInTheDocument();
    expect(screen.queryByText("Disqualifiés")).not.toBeInTheDocument();
  });

  it("annonce le total comme un nombre de participants, pas de partants", async () => {
    // `course_summary` additionne finishers + non_finishers + unknown, et range
    // les DNS dans le deuxième : le chiffre compte tous ceux qui figurent sur
    // l'épreuve, y compris ceux qui n'ont jamais pris le départ (#322).
    await afficher();

    expect(screen.getByText("Participants")).toBeInTheDocument();
    // Insensible à la casse et non ancré : le mot est aussi rendu en minuscule
    // dans le pied du tableau, par `RaceFinishers`, sur ce même `summary.total`.
    // Un `queryByText("Partants")` exact affirmait une absence sans la vérifier.
    expect(screen.queryByText(/partants/i)).not.toBeInTheDocument();
  });

  it("demande la page voulue au classement, et la synthèse sans aucun paramètre", async () => {
    await afficher({ page: "3", q: "lemee", scope: "club" });

    expect(getCourse).toHaveBeenCalledWith(1, { page: 3, q: "lemee", scope: "club" });
    expect(getCourseSummary).toHaveBeenCalledWith(1);
  });

  it.each([undefined, "0", "-2", "abc", "1.5"])(
    "traite un numéro de page illisible (%s) comme la première, sans erreur",
    async (page) => {
      await afficher({ page });
      expect(getCourse).toHaveBeenCalledWith(1, { page: 1, q: undefined, scope: undefined });
    },
  );

  it("ne transmet pas une recherche composée d'espaces", async () => {
    await afficher({ q: "   " });
    expect(getCourse).toHaveBeenCalledWith(1, { page: 1, q: undefined, scope: undefined });
  });

  it("rapporte les pourcentages de catégorie à TOUTES les catégories, pas aux 8 rendues", async () => {
    // 284 sur 1000 renseignées = 28,4 %. Les rapporter à la somme des deux
    // catégories affichées (500) donnerait 56,8 % — chaque barre gonflée, et
    // un total à 100 % que la réalité ne fait pas.
    await afficher();
    expect(screen.getByText("28,4%")).toBeInTheDocument();
    expect(screen.getByText("21,6%")).toBeInTheDocument();
  });

  it("ne transforme pas une panne du backend en « épreuve introuvable »", async () => {
    // Un 500 sur la seule synthèse ferait sinon disparaître en 404 une page
    // parfaitement valide : indiscernable d'un lien mort, invisible en supervision.
    getCourseSummary.mockRejectedValue(new ApiError(500, "Boum"));
    await expect(afficher()).rejects.toThrow("Boum");
  });

  it("rend 404 sur une épreuve réellement absente", async () => {
    getCourse.mockRejectedValue(new ApiError(404, "Course introuvable"));
    await expect(afficher()).rejects.toThrow("notFound");
  });

  it("rend 404 quand un id inconnu fait aussi 404 sur les sources", async () => {
    // Le cas réel : les trois routes répondent 404 pour le même id absent. Sans
    // `.catch` sur les sources, `Promise.all` rejetait avant d'atteindre le
    // `notFound()`, et le visiteur tombait sur l'écran d'erreur générique là où
    // la page « épreuve introuvable » l'attendait (#468).
    const absente = () => new ApiError(404, "Course introuvable");
    getCourse.mockRejectedValue(absente());
    getCourseSummary.mockRejectedValue(absente());
    getCourseSources.mockRejectedValue(absente());

    await expect(afficher()).rejects.toThrow("notFound");
  });

  it("affiche l'épreuve même si la seule route des sources répond 404", async () => {
    // Les sources ne conditionnent jamais le 404 : une épreuve sans source
    // migrée reste une épreuve valide (#284), elle n'affiche aucun chip.
    getCourseSources.mockRejectedValue(new ApiError(404, "Pas de sources"));

    await afficher();

    expect(screen.getByText("Participants")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Klikego/ })).not.toBeInTheDocument();
  });

  it("laisse remonter une panne de la route des sources", async () => {
    // Le `.catch` ne rattrape que le 404 : un 500 doit rester visible en
    // supervision plutôt que d'effacer silencieusement les sources.
    getCourseSources.mockRejectedValue(new ApiError(500, "Boum"));
    await expect(afficher()).rejects.toThrow("Boum");
  });

  it("affiche une épreuve vide sans NaN ni histogramme", async () => {
    getCourse.mockResolvedValue({
      course: COURSE,
      participations: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    getCourseSummary.mockResolvedValue({
      total: 0,
      finishers: 0,
      non_finishers: 0,
      dnf: 0,
      dns: 0,
      dsq: 0,
      unknown: 0,
      tcn_count: 0,
      male: 0,
      female: 0,
      categories: [],
      categories_total: 0,
      clubs: [],
      histogram: null,
      split_keys: [],
    } satisfies CourseSummary);

    const { container } = await afficher();

    expect(container.textContent).not.toContain("NaN");
    expect(screen.queryByText(/Distribution des temps/)).not.toBeInTheDocument();
    expect(screen.getByText("Catégories non renseignées")).toBeInTheDocument();
    expect(screen.getByText("Clubs non renseignés")).toBeInTheDocument();
  });

  it("demande les sources en même temps que la synthèse", async () => {
    await afficher();
    expect(getCourseSources).toHaveBeenCalledWith(1);
  });

  it("affiche une unique source sans la qualifier d'active ou de passive", async () => {
    await afficher();
    const lien = screen.getByRole("link", { name: /Klikego/ });
    expect(lien).toHaveAttribute("href", "https://exemple.fr/x");
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.queryByText("Source active")).not.toBeInTheDocument();
  });

  it("distingue la source active des autres quand une épreuve en a plusieurs", async () => {
    getCourseSources.mockResolvedValue([
      { id: 1, url: "https://exemple.fr/actif", provider: "klikego", is_active: true, last_scraped_at: null },
      { id: 2, url: "https://exemple.fr/passif", provider: "breizhchrono", is_active: false, last_scraped_at: null },
    ] satisfies CourseSource[]);

    await afficher();

    const actif = screen.getByRole("link", { name: /Klikego/ });
    expect(actif).toHaveAttribute("href", "https://exemple.fr/actif");
    const passif = screen.getByRole("link", { name: /Breizh Chrono/ });
    expect(passif).toHaveAttribute("href", "https://exemple.fr/passif");
    expect(screen.getByText("Source active")).toBeInTheDocument();
    expect(screen.getByText("Autre source")).toBeInTheDocument();
  });

  it("n'affiche aucun chip de source quand l'épreuve n'en a aucune", async () => {
    getCourseSources.mockResolvedValue([]);
    await afficher();
    expect(screen.queryByRole("link", { name: /Klikego/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/^Source/)).not.toBeInTheDocument();
  });
});
