import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { Participation } from "@/lib/types";

const getAthlete = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: { getAthlete: (id: number) => getAthlete(id) },
}));

vi.mock("next/navigation", () => ({ notFound: vi.fn() }));

import AthletePage from "./page";

const ATHLETE = { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" };

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: ATHLETE,
    course: {
      id: over.id,
      name: over.course?.name ?? `Course ${over.id}`,
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
      ...(over.course ?? {}),
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: "01:59:00",
    status: over.status ?? "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    course_finishers: over.course_finishers,
  };
}

async function renderAthlete(participations: Participation[]) {
  getAthlete.mockResolvedValue({ athlete: ATHLETE, participations });
  const ui = await AthletePage({ params: Promise.resolve({ id: "7" }) });
  return render(ui);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AthletePage", () => {
  it("retient le meilleur ratio, pas la meilleure place", async () => {
    await renderAthlete([
      part({ id: 1, rank_overall: 42, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 80 }),
    ]);

    expect(screen.getByText("Meilleur ratio")).toBeInTheDocument();
    expect(screen.getByText("Top 14%")).toBeInTheDocument();
    expect(screen.getByText("42e sur 300")).toBeInTheDocument();
    // La tuile « Meilleure place » garde le rang absolu minimum. On cible la
    // tuile elle-même (via son libellé) plutôt que la page entière, sans quoi
    // le test resterait vert même si la tuile disparaissait — « 20 » apparaît
    // aussi dans la pastille de la ligne correspondante du tableau.
    const label = screen.getByText("Meilleure place");
    const tile = label.parentElement?.parentElement;
    expect(tile).not.toBeNull();
    expect(within(tile as HTMLElement).getByText("20")).toBeInTheDocument();
  });

  it("affiche le nombre de classés à côté de la place, dans le tableau", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 42, course_finishers: 300 })]);

    expect(screen.getByText("/300")).toBeInTheDocument();
  });

  it("retombe sur la place seule quand le classement est incohérent", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 42, course_finishers: 20 })]);

    // Ni le « /N » de la ligne, ni un percentile : la place reste seule.
    expect(screen.queryByText("/20")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Top \d+%$/)).not.toBeInTheDocument();
    expect(screen.getByText("Meilleur ratio")).toBeInTheDocument();
    // AC3 : « incomplete » ne déclenche PAS le signal `is_reliable=false`.
    expect(screen.queryByTestId("unreliable-marker")).not.toBeInTheDocument();
  });

  it("signale visuellement une course non fiable (AC1) avec tooltip FR (AC2)", async () => {
    await renderAthlete([
      part({
        id: 1,
        rank_overall: 3,
        course_finishers: 300,
        course: {
          id: 1,
          name: "Course 1",
          event_date: "2026-05-16",
          event_type: "triathlon-m",
          provider: "manuel",
          source_url: "",
          is_relay: false,
          is_reliable: false,
          quality_issues: { duplicate_bib: 2, rank_gap: 1 },
        },
      }),
    ]);

    const marker = screen.getByTestId("unreliable-marker");
    expect(marker).toBeInTheDocument();
    // AC2 : tooltip natif via `title`, en français.
    const title = marker.getAttribute("title") ?? "";
    expect(title).toContain("2 dossards en doublon");
    expect(title).toContain("1 trou dans le classement");
    // AC1 bis : le « /N » disparaît quand la course est non fiable.
    expect(screen.queryByText("/300")).not.toBeInTheDocument();
  });

  it("rend un tooltip générique si `is_reliable=false` sans quality_issues détaillé", async () => {
    // Cas plausible : ancien import où is_reliable a été mis à false sans
    // détail (backfill, migration). L'utilisateur doit tout de même comprendre
    // pourquoi le ratio manque.
    await renderAthlete([
      part({
        id: 1,
        rank_overall: 3,
        course_finishers: 300,
        course: {
          id: 1,
          name: "Course 1",
          event_date: "2026-05-16",
          event_type: "triathlon-m",
          provider: "manuel",
          source_url: "",
          is_relay: false,
          is_reliable: false,
        },
      }),
    ]);

    const marker = screen.getByTestId("unreliable-marker");
    expect(marker.getAttribute("title") ?? "").toMatch(/fiabilité/i);
  });

  // Cellule « Place » d'un non-finisher (issue #125) : plutôt qu'un tiret muet,
  // on rend le sigle du statut. Texte sobre (pas de badge rouge alarmant : les
  // non-finishers sont un état normal, cf. non-goals). DSQ garde son rang entre
  // parenthèses si le chronométreur l'a fourni.
  it("affiche « DNF » à la place du tiret pour un abandon sans rang (AC1)", async () => {
    // Ciblage sur la ligne du tableau (par son lien) : « — » apparaît aussi
    // dans les StatCards vides du haut de page, hors périmètre de cette cellule.
    const { container } = await renderAthlete([part({ id: 1, status: "DNF" })]);
    const row = container.querySelector<HTMLElement>("a[href='/courses/1/participations/1']");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("DNF")).toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("—")).not.toBeInTheDocument();
  });

  it("affiche « DNS » pour un non-partant sans rang (AC2)", async () => {
    await renderAthlete([part({ id: 1, status: "DNS" })]);
    expect(screen.getByText("DNS")).toBeInTheDocument();
  });

  it("affiche « DSQ » pour une disqualification sans rang (AC2)", async () => {
    await renderAthlete([part({ id: 1, status: "DSQ" })]);
    expect(screen.getByText("DSQ")).toBeInTheDocument();
  });

  it("affiche « DSQ(42/300) » quand un rang provisoire subsiste sur une course fiable", async () => {
    // Le chronométreur a laissé un rang malgré la disqualification. On rend le
    // rang entre parenthèses, avec le /N habituel des finishers classés.
    const { container } = await renderAthlete([
      part({ id: 1, status: "DSQ", rank_overall: 42, course_finishers: 300 }),
    ]);
    expect(screen.getByText("DSQ(42/300)")).toBeInTheDocument();
    // Aucune pastille orange de finisher dans la ligne : le rang est
    // descriptif, pas glorieux. La StatCard « Meilleure place » du haut de
    // page peut encore afficher « 42 », hors périmètre.
    const row = container.querySelector<HTMLElement>("a[href='/courses/1/participations/1']");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).queryByText(/^42$/)).not.toBeInTheDocument();
  });

  it("masque le /N sur un DSQ classé si la course est non fiable", async () => {
    // Cohérent avec le comportement finisher : sur is_reliable=false, le
    // dénominateur disparaît (il serait faux), mais on garde le rang brut
    // fourni par le chronométreur. Le marker ⚠ signale la limite.
    await renderAthlete([
      part({
        id: 1,
        status: "DSQ",
        rank_overall: 42,
        course_finishers: 300,
        course: {
          id: 1,
          name: "Course 1",
          event_date: "2026-05-16",
          event_type: "triathlon-m",
          provider: "manuel",
          source_url: "",
          is_relay: false,
          is_reliable: false,
        },
      }),
    ]);
    expect(screen.getByText("DSQ(42)")).toBeInTheDocument();
    expect(screen.queryByText("DSQ(42/300)")).not.toBeInTheDocument();
    expect(screen.getByTestId("unreliable-marker")).toBeInTheDocument();
  });

  it("garde le marker ⚠ à côté d'un statut de non-finisher (AC5)", async () => {
    // AC5 : le signal is_reliable=false est indépendant du rang et du statut.
    // Il doit apparaître sur un DNF non fiable, alors qu'aujourd'hui le marker
    // n'est rendu que dans la branche « rang présent ».
    await renderAthlete([
      part({
        id: 1,
        status: "DNF",
        course: {
          id: 1,
          name: "Course 1",
          event_date: "2026-05-16",
          event_type: "triathlon-m",
          provider: "manuel",
          source_url: "",
          is_relay: false,
          is_reliable: false,
        },
      }),
    ]);
    expect(screen.getByText("DNF")).toBeInTheDocument();
    expect(screen.getByTestId("unreliable-marker")).toBeInTheDocument();
  });

  it("garde le tiret muet pour un finisher sans rang (AC3)", async () => {
    // Statut « finisher » sans rang connu (course en cours, données
    // incomplètes) : on ne change pas le comportement existant. On cible la
    // ligne du tableau (via son lien) parce que d'autres cellules de la page
    // affichent aussi un « — » quand une stat manque.
    const { container } = await renderAthlete([part({ id: 1, status: "finisher" })]);
    const row = container.querySelector<HTMLElement>("a[href='/courses/1/participations/1']");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("—")).toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("DNF")).not.toBeInTheDocument();
  });

  it("ouvre le détail de la participation, et non plus la page de la course", async () => {
    const { container } = await renderAthlete([part({ id: 1, rank_overall: 12 })]);

    expect(container.querySelector("a[href='/courses/1/participations/1']")).not.toBeNull();
    expect(container.querySelector("a[href='/courses/1']")).toBeNull();
  });
});
