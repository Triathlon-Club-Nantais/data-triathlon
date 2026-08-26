import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { dansLesCartes } from "@/test/cartes";
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
// lui-même ailleurs. Ici, un visiteur anonyme et des requêtes neutres par
// défaut : le tableau filtré doit être exactement celui d'un public sans
// pouvoir. `useSessionMock` reste un `vi.fn()` — jamais réécrit dans son
// défaut — pour qu'un unique describe dédié (plus bas) puisse le redéfinir
// temporairement sans toucher ce mock global (revue finale #461, point 4).
const { useSessionMock } = vi.hoisted(() => ({
  useSessionMock: vi.fn<() => { data: { permissions: string[] } | null }>(() => ({ data: null })),
}));
vi.mock("@/lib/queries/auth", () => ({
  useSession: useSessionMock,
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
  // Scopé à la grille quand elle est rendue : depuis #461, la même ligne
  // existe aussi dans l'arbre carte (masqué par CSS, toujours dans le DOM),
  // et `getByRole` n'est pas concerné par l'exclusion de `test/setup.ts`,
  // réservée aux requêtes texte. L'état vide de filtre ne rend ni l'un ni
  // l'autre arbre.
  const grille = screen.queryByTestId("epreuves-grille");
  const scope = grille ? within(grille) : screen;
  return scope
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

  // ── Structure de tableau (#481, A11Y-3) ────────────────────────────────────

  it("s'annonce comme un tableau et nomme ses colonnes", () => {
    render(<EventsTable participations={threeSeasons()} athleteId={7} athleteName="Jean DUPONT" />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    for (const nom of ["Date", "Épreuve", "Type", "Format", "Temps final", "Place"]) {
      expect(screen.getByRole("columnheader", { name: nom })).toBeInTheDocument();
    }
    // Sept colonnes, la dernière nommée en `sr-only` : un `<th>` vide est une
    // colonne anonyme, et sa flèche était annoncée à chaque ligne (revue UI/UX
    // #481).
    expect(screen.getAllByRole("columnheader")).toHaveLength(7);
    expect(screen.getByRole("columnheader", { name: "Ouvrir" })).toBeInTheDocument();
  });

  it("groupe chaque entrée dans son propre rowgroup, ligne et sous-ligne ensemble", () => {
    // Le trait de séparation porte sur le couple, jamais sur chaque moitié : il
    // vivait sur un `<div>` enveloppant qu'un tableau n'autorise plus, et c'est
    // le `<tbody>` qui le reprend (#481, D4 ; invariant de #270).
    const [avecPreuve] = threeSeasons();
    render(
      <EventsTable
        participations={[{ ...avecPreuve, evidence_url: "https://exemple.fr/preuve" }]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    const corps = screen.getAllByRole("rowgroup").filter((g) => g.tagName === "TBODY");
    expect(corps).toHaveLength(1);
    expect(within(corps[0]).getAllByRole("row")).toHaveLength(2);
    expect(within(corps[0]).getByRole("link", { name: /Voir la preuve/ })).toBeInTheDocument();
  });

  it("déclare la portée de la sous-ligne en ARIA autant qu'en HTML", () => {
    // `colSpan` est une sémantique de tableau comme les autres : la surcharge de
    // `display` qui impose de redéclarer `role="cell"` peut la faire tomber elle
    // aussi. Sans `aria-colspan`, la sous-ligne de preuve est exposée comme une
    // cellule de la seule première colonne (revue de code #481).
    const [avecPreuve] = threeSeasons();
    render(
      <EventsTable
        participations={[{ ...avecPreuve, evidence_url: "https://exemple.fr/preuve" }]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    // Scopé à la grille (#461) : la carte rend la même preuve, hors tableau.
    const sousLigne = within(screen.getByTestId("epreuves-grille"))
      .getByRole("link", { name: /Voir la preuve/ })
      .closest("td")!;
    expect(sousLigne).toHaveAttribute("colspan", "7");
    expect(sousLigne).toHaveAttribute("aria-colspan", "7");
  });

  it("n'offre qu'un arrêt clavier par ligne, la sous-ligne étant une ligne à part", () => {
    // FR-011 se compte **par `<tr>`**, jamais par entrée : une entrée à preuve
    // porte légitimement deux éléments focalisables, répartis sur ses deux
    // lignes (contrat C3).
    const [avecPreuve] = threeSeasons();
    render(
      <EventsTable
        participations={[{ ...avecPreuve, evidence_url: "https://exemple.fr/preuve" }]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    for (const ligne of screen.getAllByRole("row")) {
      expect(
        ligne.querySelectorAll("a[href], button, input, select, textarea").length,
      ).toBeLessThanOrEqual(1);
    }
  });

  it("ne rend aucun tableau sur un athlète sans résultat : cette liste masque déjà son en-tête", () => {
    render(<EventsTable participations={[]} athleteId={7} athleteName="Jean DUPONT" />);

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("Aucun résultat pour cet athlète")).toBeInTheDocument();
  });
});

describe("rendu carte sous md", () => {
  const cartes = () => dansLesCartes("epreuves-cartes");

  it("bascule la grille et les cartes aux seuils annoncés", () => {
    render(
      <EventsTable
        participations={[participation(1, { name: "Triathlon de Nantes" })]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    expect(screen.getByTestId("epreuves-grille").className).toContain("hidden min-[1145px]:block");
    expect(screen.getByTestId("epreuves-cartes").className).toContain("min-[1145px]:hidden");
  });

  it("porte date, épreuve, temps et place dans la carte", () => {
    render(
      <EventsTable
        participations={[{ ...participation(1, { name: "Triathlon de Nantes" }), rank_overall: 2 }]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    const carte = cartes();
    expect(carte.texte("16/05/2026")).toBeTruthy();
    expect(carte.texte("Triathlon de Nantes")).toBeTruthy();
    expect(carte.texte("01:59:00")).toBeTruthy();
    expect(carte.texte("2")).toBeTruthy();
  });

  it("garde la preuve dans la carte, hors du lien de la ligne", () => {
    render(
      <EventsTable
        participations={[
          {
            ...participation(1, { name: "Triathlon de Nantes" }),
            evidence_url: "https://example.org/p.jpg",
          },
        ]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    const carte = cartes();
    const preuve = carte.getByRole("link", { name: /Voir la preuve/ });
    expect(preuve).toHaveAttribute("href", "https://example.org/p.jpg");
    expect(carte.getByRole("link", { name: /Triathlon de Nantes/ })).not.toContainElement(preuve);
  });
});

// La spec (#461, preuve de test n°6) : ce qui doit être vérifié n'est pas
// l'unicité du montage de `ParticipationAdminActions`, mais que sa sous-ligne
// existe aussi dans l'arbre carte — l'oublier retirerait aux administrateurs,
// sur téléphone, des gestes qu'ils ont sur écran large. Le mock global de
// `useSession` (« un visiteur anonyme ») rend ce cas irreprésentable dans les
// autres tests du fichier : `ParticipationAdminActions` se rend nul dans les
// deux arbres, donc supprimer sa ligne de rendu dans la carte ne ferait
// rougir aucun test existant. D'où ce describe dédié, seul à redéfinir
// `useSessionMock` — le mock global du fichier reste inchangé.
describe("actions d'administration dans la carte (revue finale #461, point 4)", () => {
  const cartes = () => dansLesCartes("epreuves-cartes");

  beforeEach(() => {
    // `participations:delete` suffit à faire apparaître la sous-ligne
    // d'actions (voir `ParticipationAdminActions.tsx`) : le geste précis
    // importe peu ici, seule compte sa présence dans l'arbre carte.
    useSessionMock.mockReturnValue({ data: { permissions: ["participations:delete"] } });
  });

  afterEach(() => {
    useSessionMock.mockReturnValue({ data: null });
  });

  it("offre le geste de suppression aussi dans l'arbre carte", async () => {
    render(
      <EventsTable
        participations={[participation(1, { name: "Triathlon de Nantes" })]}
        athleteId={7}
        athleteName="Jean DUPONT"
      />,
    );

    expect(
      await cartes().findByRole("button", { name: /supprimer le résultat/i }),
    ).toBeInTheDocument();
  });
});
