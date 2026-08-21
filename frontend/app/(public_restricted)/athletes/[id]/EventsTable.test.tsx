import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Participation } from "@/lib/types";

const push = vi.fn();
let searchParams = new URLSearchParams();

// `useRouter` reste moqué alors que le composant ne s'en sert pas : c'est ce qui
// permet d'affirmer qu'aucune navigation n'est déclenchée (#328) — ni `?season=`
// ni `?discipline=` n'est lu par un rendu serveur de cette page.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/athletes/7",
  useSearchParams: () => searchParams,
}));

// `ParticipationAdminActions` vit sous chaque ligne depuis #439 et se teste pour
// lui-même ailleurs. Ici, un visiteur anonyme et des requêtes neutres : le
// tableau filtré doit être exactement celui d'un public sans pouvoir.
vi.mock("@/lib/queries/auth", () => ({
  useSession: () => ({ data: null }),
}));
vi.mock("@/lib/queries/admin", () => ({
  useAdminAthlete: () => ({ data: undefined }),
  useUpdateAthlete: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteParticipation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useReassignParticipation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useAdminAthleteSearch: () => ({ data: undefined, isFetching: false }),
}));

import { EventsTable } from "./EventsTable";

const ATHLETE = { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" };

function participation(
  id: number,
  over: { date?: string | null; type?: string; name?: string } = {},
): Participation {
  return {
    id,
    athlete: ATHLETE,
    course: {
      id,
      name: over.name ?? `Course ${id}`,
      event_date: over.date === undefined ? "2026-05-16" : over.date,
      event_type: over.type ?? "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    is_tcn: true,
    category: null,
    bib_number: null,
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    total_time: "01:59:00",
    status: "finisher",
    is_relay: false,
    team_name: null,
    evidence_url: null,
    is_pending_validation: false,
    is_rejected: false,
    splits: null,
    created_at: null,
  };
}

let pushState: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  push.mockClear();
  searchParams = new URLSearchParams();
  // Implémentation neutre : sans elle, le vrai `pushState` s'exécute et chaque
  // test laisse l'URL de jsdom déplacée pour le suivant.
  pushState = vi.spyOn(window.history, "pushState").mockImplementation(() => {});
});

afterEach(() => {
  pushState.mockRestore();
});

/** Trois saisons, deux disciplines : le jeu de référence des filtres. */
function threeSeasons(): Participation[] {
  return [
    participation(1, { date: "2026-05-16", type: "triathlon-m", name: "Tri de Nantes" }),
    participation(2, { date: "2024-10-05", type: "triathlon-l", name: "Tri de Vannes" }),
    participation(3, { date: "2024-11-09", type: "trail", name: "Trail des Coteaux" }),
  ];
}

/** Les lignes du tableau : chacune est un lien vers le détail de participation. */
function rowLinks(): string[] {
  return screen
    .queryAllByRole("link")
    .map((a) => a.getAttribute("href") ?? "")
    .filter((href) => href.startsWith("/courses/"));
}

describe("EventsTable", () => {
  it("liste toutes les épreuves quand aucun filtre n'est posé", () => {
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(rowLinks()).toHaveLength(3);
    expect(screen.getByText("Tri de Nantes")).toBeInTheDocument();
    expect(screen.getByText("Trail des Coteaux")).toBeInTheDocument();
  });

  it("annonce le compte des épreuves affichées", () => {
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(screen.getByRole("status")).toHaveTextContent("3 épreuves");
  });

  it("n'offre aucun filtre quand il n'y a rien à choisir", () => {
    // Une seule saison, une seule discipline : 47 % des membres du club n'ont
    // qu'une épreuve — leur profil ne doit pas porter deux sélecteurs inertes.
    render(<EventsTable participations={[participation(1)]} athleteId={7} athleteName="Jean DUPONT" />);

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 épreuve");
  });

  it("propose une entrée par saison représentée, la plus récente d'abord", async () => {
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    await userEvent.click(screen.getByRole("combobox", { name: /saison/i }));
    const options = (await screen.findAllByRole("option")).map((o) => o.textContent);
    expect(options).toEqual(["Toutes les saisons", "Saison 2025 — 2026", "Saison 2024 — 2025"]);
  });

  it("groupe les formats d'une même discipline en une seule entrée", async () => {
    // « Triathlon M » et « Triathlon L » sont deux formats d'une discipline : le
    // filtre parle discipline, la colonne Format dit déjà le reste.
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    await userEvent.click(screen.getByRole("combobox", { name: /discipline/i }));
    const options = (await screen.findAllByRole("option")).map((o) => o.textContent);
    expect(options).toEqual(["Toutes les disciplines", "Triathlon", "Trail"]);
  });

  it("restreint le tableau à la saison portée par l'URL", () => {
    searchParams = new URLSearchParams("season=2024");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(rowLinks()).toHaveLength(2);
    expect(screen.queryByText("Tri de Nantes")).not.toBeInTheDocument();
    expect(screen.getByText("Tri de Vannes")).toBeInTheDocument();
  });

  it("restreint le tableau à la discipline portée par l'URL, tous formats confondus", () => {
    searchParams = new URLSearchParams("discipline=triathlon");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(rowLinks()).toHaveLength(2);
    expect(screen.getByText("Tri de Nantes")).toBeInTheDocument();
    expect(screen.queryByText("Trail des Coteaux")).not.toBeInTheDocument();
  });

  it("croise les deux filtres", () => {
    searchParams = new URLSearchParams("season=2024&discipline=triathlon");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(rowLinks()).toHaveLength(1);
    expect(screen.getByText("Tri de Vannes")).toBeInTheDocument();
  });

  it("dit combien de lignes le filtre retient sur le total", () => {
    searchParams = new URLSearchParams("discipline=trail");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(screen.getByRole("status")).toHaveTextContent("1 épreuve sur 3");
  });

  it("retombe silencieusement sur tout afficher pour une valeur absente des épreuves", () => {
    searchParams = new URLSearchParams("season=1999&discipline=natation");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(rowLinks()).toHaveLength(3);
    expect(screen.getByRole("status")).toHaveTextContent("3 épreuves");
  });

  it("écrit le choix de saison dans l'URL par l'historique, sans navigation", async () => {
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    await userEvent.click(screen.getByRole("combobox", { name: /saison/i }));
    await userEvent.click(await screen.findByRole("option", { name: "Saison 2024 — 2025" }));

    expect(pushState).toHaveBeenCalledWith(null, "", "/athletes/7?season=2024");
    expect(push).not.toHaveBeenCalled();
  });

  it("écrit le choix de discipline dans l'URL sans écraser les autres paramètres", async () => {
    searchParams = new URLSearchParams("season=2024");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    await userEvent.click(screen.getByRole("combobox", { name: /discipline/i }));
    await userEvent.click(await screen.findByRole("option", { name: "Trail" }));

    const url = pushState.mock.calls[0][2] as string;
    expect(url).toContain("season=2024");
    expect(url).toContain("discipline=trail");
  });

  it("retire le paramètre quand on revient à toutes les saisons", async () => {
    searchParams = new URLSearchParams("season=2024");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    await userEvent.click(screen.getByRole("combobox", { name: /saison/i }));
    await userEvent.click(await screen.findByRole("option", { name: "Toutes les saisons" }));

    expect(pushState).toHaveBeenCalledWith(null, "", "/athletes/7");
  });

  it("offre une sortie quand le croisement des filtres ne rend aucune ligne", async () => {
    searchParams = new URLSearchParams("season=2025&discipline=trail");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(rowLinks()).toHaveLength(0);
    expect(screen.getByText(/aucune épreuve/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /toutes les épreuves/i }));
    expect(pushState).toHaveBeenCalledWith(null, "", "/athletes/7");
  });

  it("garde l'état vide de l'athlète sans épreuve, filtres compris", () => {
    render(<EventsTable participations={[]} athleteId={7} athleteName="Jean DUPONT" />);

    expect(screen.getByText("Aucun résultat pour cet athlète")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("filtre sur la saison de l'épreuve, pas sur son année civile", () => {
    // Saison = 1ᵉʳ sept → 31 août : une épreuve du 5 octobre 2024 appartient à
    // la saison 2024 — 2025, celle du 16 mai 2026 à la saison 2025 — 2026.
    searchParams = new URLSearchParams("season=2025");
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(rowLinks()).toHaveLength(1);
    expect(screen.getByText("Tri de Nantes")).toBeInTheDocument();
  });

  it("écarte une épreuve sans date dès qu'une saison est demandée, et la garde sinon", () => {
    const parts = [...threeSeasons(), participation(4, { date: null, name: "Course sans date" })];

    const sansFiltre = render(<EventsTable participations={parts} athleteId={7} athleteName="Jean DUPONT" />);
    expect(screen.getByText("Course sans date")).toBeInTheDocument();
    sansFiltre.unmount();

    searchParams = new URLSearchParams("season=2024");
    render(<EventsTable participations={parts} athleteId={7} athleteName="Jean DUPONT" />);
    expect(screen.queryByText("Course sans date")).not.toBeInTheDocument();
  });
});
