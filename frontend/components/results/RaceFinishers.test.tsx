// frontend/components/results/RaceFinishers.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { StrictMode, type ReactNode } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CourseSummary, Participation } from "@/lib/types";
import { SCOPE_CLUB, SCOPE_PARAM } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";
import { writeAthlete } from "@/components/layout/AthletePicker";
import { dansLesCartes } from "@/test/cartes";

const push = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/courses/1",
  useSearchParams: () => searchParams,
}));

// `prefetch` ne se reflète sur aucun attribut du DOM : sans ce miroir, rien ne
// distinguerait une ligne préchargée d'une autre — et #481 en dépend, la phase
// d'attente étant sautée sur une route déjà préchargée. Même patron que
// `components/dashboard/RecentCourses.test.tsx` (#425).
vi.mock("next/link", () => ({
  default: ({
    href,
    prefetch,
    children,
    ...rest
  }: {
    href: string;
    prefetch?: boolean;
    children?: ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} data-prefetch={String(prefetch)} {...rest}>
      {children}
    </a>
  ),
  // Hors d'une navigation cliente, Next rend `{ pending: false }` — c'est aussi
  // l'état au repos, le seul que jsdom peut observer.
  useLinkStatus: () => ({ pending: false }),
}));

import { RaceFinishers } from "./RaceFinishers";

function p(over: Partial<Participation> & { id: number; nom: string }): Participation {
  return {
    id: over.id,
    athlete: { id: over.id, nom: over.nom, prenom: "T", gender: "M", club: null },
    course: { id: 1, name: "C", event_date: null, event_type: "", provider: "", source_url: "", is_relay: false },
    club: over.club ?? null,
    is_tcn: over.is_tcn ?? false,
    category: "S4",
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: over.total_time ?? null,
    status: over.status ?? "finisher",
    is_relay: false,
    splits: over.splits ?? null,
    split_gap_ratio: over.split_gap_ratio ?? null,
    created_at: null,
  } as Participation;
}

function synthese(over: Partial<CourseSummary> = {}): CourseSummary {
  return {
    total: 3,
    finishers: 1,
    non_finishers: 2,
    dnf: 2,
    dns: 0,
    dsq: 0,
    unknown: 0,
    tcn_count: 0,
    male: 3,
    female: 0,
    categories: [],
    categories_total: 0,
    clubs: [],
    clubs_total: 0,
    histogram: null,
    split_keys: [],
    split_gap_median: null,
    split_gap_rows: 0,
    ...over,
  };
}

const data = [
  p({ id: 1, nom: "FINISHER", status: "finisher", rank_overall: 1, total_time: "00:55:00" }),
  p({ id: 2, nom: "DNSGUY", status: "DNS" }),
  p({ id: 3, nom: "DNFGUY", status: "DNF", total_time: "01:10:00" }),
];

function afficher(over: Partial<Parameters<typeof RaceFinishers>[0]> = {}) {
  return render(
    <RaceFinishers
      participations={data}
      summary={synthese()}
      total={3}
      page={1}
      pageSize={20}
      {...over}
    />,
  );
}

beforeEach(() => {
  push.mockClear();
  searchParams = new URLSearchParams();
});

describe("RaceFinishers", () => {
  it("affiche un badge DNS/DNF pour les non-finishers", () => {
    afficher();
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.getByText("DNF")).toBeInTheDocument();
  });

  it("écrit le club du participant TCN en `--tcn-orange-deeper`, seul token à tenir 4,5:1 (A11Y-4)", () => {
    // Même défaut que PlaceBadge/Eyebrow/SegmentedControl : --tcn-orange en
    // texte 13px ne tient que 3,32 à 3,68:1 selon le fond (revue UI/UX #465).
    afficher({
      participations: [
        p({ id: 1, nom: "FINISHER", status: "finisher", rank_overall: 1, total_time: "00:55:00", club: "TRIATHLON CLUB NANTAIS", is_tcn: true }),
      ],
    });
    expect(screen.getByText("TRIATHLON CLUB NANTAIS").style.color).toBe("var(--tcn-orange-deeper)");
  });

  it("ventile le pied de tableau : participants · finishers · abandons (pas « X finishers au total »)", () => {
    afficher();
    expect(screen.getByText("3 participants · 1 finisher · 2 abandons")).toBeInTheDocument();
  });

  it("ajoute les « indéterminés » au pied de tableau pour réconcilier avec le total", () => {
    afficher({ summary: synthese({ total: 4, finishers: 1, non_finishers: 1, dnf: 1, unknown: 2 }) });
    expect(
      screen.getByText("4 participants · 1 finisher · 1 abandon · 2 indéterminés"),
    ).toBeInTheDocument();
  });

  it("prend son décompte dans la synthèse, pas dans la page affichée", () => {
    // Une page de 3 lignes sur une épreuve de 1811 : le pied annonce l'épreuve.
    afficher({
      summary: synthese({ total: 1811, finishers: 1768, non_finishers: 43, dnf: 43 }),
      total: 1811,
    });
    expect(screen.getByText(/1811 participants/)).toBeInTheDocument();
  });

  it("distingue abandons, non-partants et disqualifiés au pied de tableau (#331)", () => {
    afficher({
      summary: synthese({ total: 11, finishers: 3, non_finishers: 8, dnf: 5, dns: 2, dsq: 1 }),
    });
    expect(
      screen.getByText("11 participants · 3 finishers · 5 abandons · 2 non-partants · 1 disqualifié"),
    ).toBeInTheDocument();
  });

  it("ne mentionne ni non-partants ni disqualifiés quand ils sont nuls (#331)", () => {
    afficher();
    expect(screen.queryByText(/non-partant/)).not.toBeInTheDocument();
    expect(screen.queryByText(/disqualifié/)).not.toBeInTheDocument();
  });

  // ── Pagination ─────────────────────────────────────────────────────────────

  it("ne rend aucun contrôle de pagination quand la sélection tient en une page", () => {
    afficher({ total: 3, pageSize: 20 });
    expect(screen.queryByRole("navigation", { name: /pagination/i })).not.toBeInTheDocument();
  });

  it("rend des liens « Précédent » / « Suivant » portant le numéro de page", () => {
    afficher({ total: 100, pageSize: 20, page: 3 });

    expect(screen.getByLabelText("Aller à la page")).toHaveValue(3);
    expect(screen.getByText("sur 5")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Précédent/ })).toHaveAttribute("href", "/courses/1?page=2");
    expect(screen.getByRole("link", { name: /Suivant/ })).toHaveAttribute("href", "/courses/1?page=4");
  });

  it("relie « sur N » au champ de saut par aria-describedby, pas seulement par proximité visuelle (#485)", () => {
    afficher({ total: 100, pageSize: 20, page: 3 });

    const champ = screen.getByLabelText("Aller à la page");
    const idDescription = champ.getAttribute("aria-describedby");
    expect(idDescription).toBeTruthy();
    expect(document.getElementById(idDescription!)).toHaveTextContent("sur 5");
  });

  it("omet le paramètre page pour revenir à la première : l'URL par défaut reste propre", () => {
    afficher({ total: 100, pageSize: 20, page: 2 });
    expect(screen.getByRole("link", { name: /Précédent/ })).toHaveAttribute("href", "/courses/1");
  });

  it("désactive « Précédent » en première page et « Suivant » en dernière", () => {
    const { unmount } = afficher({ total: 100, pageSize: 20, page: 1 });
    expect(screen.queryByRole("link", { name: /Précédent/ })).not.toBeInTheDocument();
    unmount();

    afficher({ total: 100, pageSize: 20, page: 5 });
    expect(screen.queryByRole("link", { name: /Suivant/ })).not.toBeInTheDocument();
  });

  it("préserve les autres paramètres d'URL dans les liens de pagination", () => {
    searchParams = new URLSearchParams("q=dupont&scope=club");
    afficher({ total: 100, pageSize: 20, page: 1 });

    const suivant = screen.getByRole("link", { name: /Suivant/ }).getAttribute("href") ?? "";
    expect(suivant).toContain("q=dupont");
    expect(suivant).toContain("scope=club");
    expect(suivant).toContain("page=2");
  });

  // ── Saut de page ───────────────────────────────────────────────────────────

  it("rend des liens vers la première et la dernière page", () => {
    afficher({ total: 860, pageSize: 20, page: 21 });

    expect(screen.getByRole("link", { name: /Première/ })).toHaveAttribute("href", "/courses/1");
    expect(screen.getByRole("link", { name: /Dernière/ })).toHaveAttribute("href", "/courses/1?page=43");
  });

  it("saute à la page saisie sans perdre la recherche ni le filtre", async () => {
    searchParams = new URLSearchParams("q=dupont&scope=club");
    afficher({ total: 860, pageSize: 20, page: 1 });

    const champ = screen.getByLabelText("Aller à la page");
    await userEvent.clear(champ);
    await userEvent.type(champ, "22");
    await userEvent.click(screen.getByRole("button", { name: "Aller" }));

    const url = push.mock.calls.at(-1)?.[0] ?? "";
    expect(url).toContain("q=dupont");
    expect(url).toContain("scope=club");
    expect(url).toContain("page=22");
  });

  it("ramène une saisie hors bornes dans le classement plutôt que de la refuser", async () => {
    // « 99 » sur 43 pages veut dire « la fin ».
    afficher({ total: 860, pageSize: 20, page: 1 });

    const champ = screen.getByLabelText("Aller à la page");
    await userEvent.clear(champ);
    await userEvent.type(champ, "99");
    await userEvent.click(screen.getByRole("button", { name: "Aller" }));

    expect(push).toHaveBeenCalledWith("/courses/1?page=43");
  });

  it("omet le paramètre page quand on saute à la première", async () => {
    afficher({ total: 860, pageSize: 20, page: 5 });

    const champ = screen.getByLabelText("Aller à la page");
    await userEvent.clear(champ);
    await userEvent.type(champ, "1");
    await userEvent.click(screen.getByRole("button", { name: "Aller" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("porte les autres paramètres en champs cachés, pour un saut sans JavaScript", () => {
    searchParams = new URLSearchParams("q=dupont&page_size=50");
    afficher({ total: 860, pageSize: 50, page: 2 });

    const form = screen.getByLabelText("Aller à la page").closest("form")!;
    expect(form).toHaveAttribute("method", "get");
    // `toHaveValue` ne lit pas un champ caché : on interroge l'attribut.
    expect(form.querySelector('input[name="q"]')).toHaveAttribute("value", "dupont");
    expect(form.querySelector('input[name="page_size"]')).toHaveAttribute("value", "50");
  });

  // ── Taille de tranche ──────────────────────────────────────────────────────

  it("propose les quatre tailles de tranche, même quand tout tient en une page", () => {
    afficher({ total: 3, pageSize: 20 });

    const selecteur = screen.getByLabelText("Lignes par page");
    expect(selecteur).toBeInTheDocument();
    expect(
      Array.from(selecteur.querySelectorAll("option")).map((o) => o.textContent),
    ).toEqual(["20 lignes", "50 lignes", "200 lignes", "Tout"]);
  });

  it("pousse la taille choisie dans l'URL et revient à la première page", async () => {
    searchParams = new URLSearchParams("page=7");
    afficher({ total: 900, pageSize: 20, page: 7 });

    await userEvent.selectOptions(screen.getByLabelText("Lignes par page"), "200");

    expect(push).toHaveBeenCalledWith("/courses/1?page_size=200");
  });

  it("retire le paramètre quand on revient à la taille par défaut", async () => {
    searchParams = new URLSearchParams("page_size=200");
    afficher({ total: 900, pageSize: 200, page: 1 });

    await userEvent.selectOptions(screen.getByLabelText("Lignes par page"), "20");

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("garde le sélecteur mais retire la navigation de pages quand tout est demandé", () => {
    searchParams = new URLSearchParams("page_size=all");
    afficher({ total: 900, pageSize: null, page: 1 });

    expect(screen.getByLabelText("Lignes par page")).toHaveValue("all");
    expect(screen.queryByRole("navigation", { name: /pagination/i })).not.toBeInTheDocument();
  });

  // ── Recherche et filtre club ───────────────────────────────────────────────

  it("pousse la recherche dans l'URL et revient à la première page", async () => {
    searchParams = new URLSearchParams("page=7");
    afficher({ total: 100, pageSize: 20, page: 7 });

    await userEvent.type(screen.getByRole("searchbox"), "lemee");
    await userEvent.click(screen.getByRole("button", { name: "Chercher" }));

    expect(push).toHaveBeenCalledWith("/courses/1?q=lemee");
  });

  it("retire la recherche de l'URL quand le champ est vidé", async () => {
    searchParams = new URLSearchParams("q=lemee");
    afficher();

    await userEvent.clear(screen.getByRole("searchbox"));
    await userEvent.click(screen.getByRole("button", { name: "Chercher" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("nomme le segment « tous » avec le même mot que le reste de l'écran : participants (#343)", () => {
    afficher({ summary: synthese({ total: 1811 }) });
    expect(screen.getByText("Tous les participants (1811)")).toBeInTheDocument();
  });

  it("bascule le filtre club en paramètre d'URL et revient à la première page", async () => {
    searchParams = new URLSearchParams("page=4");
    afficher({ summary: synthese({ tcn_count: 5 }), total: 100, pageSize: 20, page: 4 });

    await userEvent.click(screen.getByRole("button", { name: /Triathlon Club Nantais/ }));

    expect(push).toHaveBeenCalledWith("/courses/1?scope=club");
  });

  it("propose le retour au début sur une page hors bornes, plutôt qu'un cul-de-sac", () => {
    searchParams = new URLSearchParams("page=99999");
    afficher({ participations: [], total: 100, pageSize: 20, page: 99999 });

    expect(screen.getByText("Cette page n'existe pas")).toBeInTheDocument();
    expect(screen.getByText(/le classement s'arrête à la page 5/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Revenir au début" })).toHaveAttribute(
      "href",
      "/courses/1",
    );
    // « Précédent » ramène à la dernière page réelle, pas à la page 99 998.
    expect(screen.getByRole("link", { name: /Précédent/ })).toHaveAttribute(
      "href",
      "/courses/1?page=5",
    );
  });

  // Rendu sous StrictMode : l'ajustement d'état se fait pendant le rendu, et le
  // double-rendu de StrictMode le rejouerait sans son garde d'égalité. Le test
  // vérifie donc les deux à la fois — la resynchronisation, et le silence de
  // React (une mise à jour pendant le rendu d'un *autre* composant, ou une
  // boucle, sortirait en console.error).
  it("resynchronise le champ de recherche quand l'URL change (retour navigateur)", () => {
    const erreurs = vi.spyOn(console, "error").mockImplementation(() => {});
    searchParams = new URLSearchParams("q=dupont");
    const { rerender } = render(
      <RaceFinishers participations={data} summary={synthese()} total={3} page={1} pageSize={20} />,
      { wrapper: StrictMode },
    );
    expect(screen.getByRole("searchbox")).toHaveValue("dupont");

    searchParams = new URLSearchParams();
    rerender(
      <RaceFinishers participations={data} summary={synthese()} total={3} page={1} pageSize={20} />,
    );
    expect(screen.getByRole("searchbox")).toHaveValue("");
    expect(erreurs).not.toHaveBeenCalled();
    erreurs.mockRestore();
  });

  it("annonce l'absence de résultat de recherche distinctement d'une épreuve vide", () => {
    searchParams = new URLSearchParams("q=zzz");
    afficher({ participations: [], total: 0 });
    expect(screen.getByText("Aucun athlète ne correspond à cette recherche")).toBeInTheDocument();
  });

  it("n'affirme pas « Cette page n'existe pas » quand la vraie cause est une recherche sans résultat (#M4)", () => {
    // `?q=zzz&page=5` : total=0 fait tomber nbPages à 1, donc page(5) > nbPages(1) —
    // mais la cause réelle est la recherche vide, pas une page hors bornes.
    searchParams = new URLSearchParams("q=zzz&page=5");
    afficher({ participations: [], total: 0, page: 5 });

    expect(screen.getByText("Aucun athlète ne correspond à cette recherche")).toBeInTheDocument();
    expect(screen.queryByText("Cette page n'existe pas")).not.toBeInTheDocument();
  });

  it("n'efface que la recherche quand le filtre club est aussi actif (tâche 8, supersède la revue #476)", async () => {
    searchParams = new URLSearchParams("q=zzz&" + SCOPE_PARAM + "=" + SCOPE_CLUB);
    afficher({ participations: [], total: 0 });

    await userEvent.click(screen.getByRole("button", { name: "Effacer la recherche" }));

    expect(push).toHaveBeenCalledWith(`/courses/1?${SCOPE_PARAM}=${SCOPE_CLUB}`);
  });

  it("ne parle pas de recherche quand seul le filtre club est actif", () => {
    // Course sans athlète TCN : « Aucun athlète ne correspond à cette recherche »
    // alors qu'aucune recherche n'a été faite.
    searchParams = new URLSearchParams(`${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ participations: [], total: 0, summary: synthese({ total: 498, tcn_count: 0 }) });

    expect(
      screen.getByText(`Aucun athlète du ${CLUB_NAME} sur cette épreuve`),
    ).toBeInTheDocument();
    expect(screen.queryByText(/correspond à cette recherche/)).not.toBeInTheDocument();
  });

  it("offre la sortie du filtre club depuis son message d'absence", async () => {
    searchParams = new URLSearchParams(`${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ participations: [], total: 0, summary: synthese({ total: 498, tcn_count: 0 }) });

    await userEvent.click(screen.getByRole("button", { name: "Voir tous les participants" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("annonce une épreuve sans aucun participant (ETAT-3)", () => {
    afficher({ participations: [], total: 0 });
    expect(screen.getByText("Aucun participant à afficher")).toBeInTheDocument();
  });

  // ── Colonnes de splits ─────────────────────────────────────────────────────

  it("tire les colonnes de splits de la synthèse, pas des lignes affichées", () => {
    // Aucune des trois lignes ne porte de split : les colonnes viennent quand
    // même de la synthèse, donc elles ne bougent pas d'une page à l'autre.
    afficher({
      summary: synthese({ split_keys: ["swim", "bike", "run"] }),
      eventType: "triathlon-m",
    });

    expect(screen.getByText("Natation")).toBeInTheDocument();
    expect(screen.getByText("Vélo")).toBeInTheDocument();
    expect(screen.getByText("Course")).toBeInTheDocument();
  });

  // ── Inter illisible (#472) ─────────────────────────────────────────────────

  // Observé en préproduction sur la course 340 : un inter valant `0-2:-15:00`.
  // Le repli `—` ne couvrait que l'absence, pas l'impossible — la chaîne partait
  // à l'écran telle quelle, indiscernable d'un chronomètre exact.
  const ILLISIBLE = "0-2:-15:00";

  function afficherInter(splits: Record<string, string> = { swim: ILLISIBLE }) {
    afficher({
      participations: [p({ id: 1, nom: "ABIME", rank_overall: 1, total_time: "01:00:00", splits })],
      summary: synthese({ split_keys: ["swim"] }),
      total: 1,
      eventType: "triathlon-m",
    });
  }

  it("ne rend pas un inter impossible comme s'il s'agissait d'un temps", () => {
    afficherInter();
    expect(screen.queryByText(ILLISIBLE)).not.toBeInTheDocument();
  });

  it("garde le marqueur d'inter illisible au-dessus du voile de la ligne (revue de code #481)", () => {
    // Le `::after` de `.tcn-rowlink__cible` couvre la ligne entière et gagne le
    // survol sur le contenu en flux des cellules voisines : sans `position`, le
    // ⚠ rendait le pointeur de la ligne et **aucune** infobulle. FR-008 nomme ce
    // marqueur parmi les comportements à préserver.
    afficherInter();

    expect(screen.getByRole("img", { name: /illisible/i }).style.position).toBe("relative");
  });

  it("signale l'inter illisible au lieu de le taire, et rappelle la valeur reçue", () => {
    // Masquer sans rien dire ferait croire que le chronométreur n'a rien publié.
    afficherInter();
    // Scopé à la grille (#461) : le même ⚠ existe dans le dépliant de la carte.
    expect(
      within(screen.getByTestId("classement-grille")).getByRole("img", { name: /illisible/i }),
    ).toHaveAccessibleName(new RegExp(ILLISIBLE));
  });

  it("laisse un inter absent en simple tiret, sans signal", () => {
    afficherInter({});
    expect(
      within(screen.getByTestId("classement-grille")).queryByRole("img", { name: /illisible/i }),
    ).not.toBeInTheDocument();
  });

  it("rend tel quel un inter parsable", () => {
    afficherInter({ swim: "00:25:00" });
    expect(screen.getByText("00:25:00")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("classement-grille")).queryByRole("img", { name: /illisible/i }),
    ).not.toBeInTheDocument();
  });

  // ── Tri par temps intermédiaire (#309) ─────────────────────────────────────

  const dataAvecSplits = [
    p({ id: 1, nom: "LENT", rank_overall: 2, total_time: "01:00:00", splits: { swim: "00:25:00" } }),
    p({ id: 2, nom: "RAPIDE", rank_overall: 1, total_time: "00:58:00", splits: { swim: "00:20:00" } }),
    // Pas de temps natation publié : doit finir en dernier une fois le tri actif.
    p({ id: 3, nom: "SANSNATATION", rank_overall: 3, total_time: "01:05:00", splits: {} }),
  ];

  function nomsAffiches() {
    return screen
      .getAllByText(/^(LENT|RAPIDE|SANSNATATION) T$/)
      .map((el) => el.textContent);
  }

  it("garde l'ordre transmis par le backend tant qu'aucun en-tête de split n'a été cliqué", () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    expect(nomsAffiches()).toEqual(["LENT T", "RAPIDE T", "SANSNATATION T"]);
  });

  it("trie en ordre croissant sur le split cliqué", async () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps.*Natation/i }));

    // RAPIDE (20 min) avant LENT (25 min) ; SANSNATATION (aucun temps) en dernier.
    expect(nomsAffiches()).toEqual(["RAPIDE T", "LENT T", "SANSNATATION T"]);
  });

  it("recliquer sur le même en-tête inverse l'ordre en décroissant", async () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    const bouton = screen.getByRole("button", { name: /Trier par temps.*Natation/i });
    await userEvent.click(bouton); // croissant : RAPIDE, LENT, SANSNATATION
    await userEvent.click(bouton); // décroissant

    // SANSNATATION (aucun temps) reste en dernier même décroissant : ce n'est
    // pas un temps nul, il n'y a simplement rien à comparer.
    expect(nomsAffiches()).toEqual(["LENT T", "RAPIDE T", "SANSNATATION T"]);
  });

  it("en-tête de split activable au clavier, avec libellé français explicite", () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    const bouton = screen.getByRole("button", { name: /Trier par temps.*Natation/i });
    expect(bouton.tagName).toBe("BUTTON");
  });

  // ── Tri par temps total ─────────────────────────────────────────────────────

  it("trie en ordre croissant sur le temps total", async () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/i }));

    // RAPIDE (00:58:00) < LENT (01:00:00) < SANSNATATION (01:05:00).
    expect(nomsAffiches()).toEqual(["RAPIDE T", "LENT T", "SANSNATATION T"]);
  });

  it("recliquer sur l'en-tête « Temps total » inverse l'ordre en décroissant", async () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    const bouton = screen.getByRole("button", { name: /Trier par temps total/i });
    await userEvent.click(bouton);
    await userEvent.click(bouton);

    expect(nomsAffiches()).toEqual(["SANSNATATION T", "LENT T", "RAPIDE T"]);
  });

  it("cliquer sur un autre en-tête repart en croissant, sans garder la direction précédente", async () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    const totalBtn = screen.getByRole("button", { name: /Trier par temps total/i });
    await userEvent.click(totalBtn);
    await userEvent.click(totalBtn); // décroissant sur le temps total

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps.*Natation/i }));

    // Nouvel en-tête : repart en croissant, pas en décroissant.
    expect(nomsAffiches()).toEqual(["RAPIDE T", "LENT T", "SANSNATATION T"]);
  });

  // ── Ouverture du détail de participation ───────────────────────────────────

  // La ligne est un **lien** depuis #481 : ce qui se vérifie n'est plus un
  // appel de navigation mais une adresse de destination. Un test sur le
  // gestionnaire de clic est précisément ce qui avait laissé passer le défaut —
  // il passait au vert sur une ligne qu'on ne pouvait ni partager ni ouvrir
  // dans un onglet (FR-010).
  it("ouvre le détail de la participation, et non plus le profil de l'athlète", () => {
    afficher();

    expect(screen.getByRole("link", { name: /Voir le détail du résultat de FINISHER/ })).toHaveAttribute(
      "href",
      "/courses/1/participations/1",
    );
  });

  it("porte une adresse de détail par ligne affichée, sans exécuter de script", () => {
    afficher();

    const adresses = screen
      .getAllByRole("row")
      .slice(1)
      .map((l) => l.querySelector("a[href]")?.getAttribute("href"));
    expect(adresses).toEqual([
      "/courses/1/participations/1",
      "/courses/1/participations/2",
      "/courses/1/participations/3",
    ]);
  });

  it("n'annonce plus la ligne comme un bouton (WCAG 4.1.2)", () => {
    // Assertion **négative**, et c'est elle qui interdit le retour du défaut :
    // un test qui ne vérifierait que la présence du lien laisserait réapparaître
    // un `role="button"` à côté.
    afficher();

    expect(screen.queryByRole("button", { name: /Voir le détail/i })).not.toBeInTheDocument();
  });

  it("n'offre qu'un arrêt clavier par ligne", () => {
    // FR-011, compté par `<tr>` : un `href` par cellule multiplierait les
    // tabulations par sept sans qu'aucune autre assertion ne bronche.
    afficher();

    for (const ligne of screen.getAllByRole("row").slice(1)) {
      expect(ligne.querySelectorAll("a[href], button, input, select, textarea")).toHaveLength(1);
    }
  });

  it("désactive le prefetch des lignes, sans quoi l'attente ne s'afficherait jamais", () => {
    // `useLinkStatus` saute la phase d'attente sur une route déjà préchargée
    // (doc de Next 16.3.1). Sans `prefetch={false}`, l'indicateur de FR-005
    // serait mort en production — et 20 routes dynamiques seraient préchargées
    // par page, le coût que #425 a déjà refusé sur `RecentCourses`.
    afficher();

    for (const ligne of screen.getAllByRole("row").slice(1)) {
      expect(ligne.querySelector("a[href]")).toHaveAttribute("data-prefetch", "false");
    }
  });

  it("porte une marque d'attente sur la ligne, toujours montée et sans mouvement", () => {
    // Toujours rendue, seule son opacité change : un indicateur monté au clic
    // déplacerait la mise en page (doc de Next), et une animation serait figée
    // sous `prefers-reduced-motion`.
    afficher();

    for (const ligne of screen.getAllByRole("row").slice(1)) {
      const marque = ligne.querySelector<HTMLElement>("[data-attente]");
      expect(marque).not.toBeNull();
      expect(marque).toHaveAttribute("aria-hidden", "true");
      expect(marque).toHaveAttribute("data-attente", "false");
    }
  });

  it("marque l'attente en pied de ligne, jamais en nappe par-dessus le texte", () => {
    // Régression bloquante relevée en revue UI/UX : une nappe couvrant la ligne
    // passe au-dessus du contenu en flux de **toutes** les cellules et faisait
    // tomber le texte à 2,50:1 (`--tcn-ink`) et 1,74:1 (colonne Club), sous le
    // plancher WCAG 1.4.3. Le filet ne recouvre aucun texte.
    afficher();

    const marque = screen.getAllByRole("row")[1].querySelector<HTMLElement>("[data-attente]")!;
    expect(marque.style.top).toBe("");
    expect(marque.style.bottom).toBe("0px");
    expect(marque.style.height).toBe("3px");
  });

  // ── Annonce du décompte / tri (WCAG 4.1.3, #477) ───────────────────────────

  it("annonce le nombre de résultats affichés dans une région role=status", () => {
    afficher();
    expect(screen.getByRole("status")).toHaveTextContent("3 résultats affichés");
  });

  it("annonce la colonne et la direction de tri une fois un en-tête cliqué", async () => {
    afficher({
      participations: [
        p({ id: 1, nom: "LENT", total_time: "01:00:00" }),
        p({ id: 2, nom: "RAPIDE", total_time: "00:58:00" }),
      ],
    });

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/i }));

    expect(screen.getByRole("status")).toHaveTextContent(/temps total.*croissant/i);
  });

  it("annonce le périmètre du tri : la tranche affichée, pas le classement", async () => {
    afficher({ total: 860, pageSize: 20 });

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/ }));

    expect(
      screen.getByRole("status").textContent,
    ).toContain("sur les 3 lignes affichées");
  });

  it("ne mentionne aucun périmètre quand tout le classement est affiché", async () => {
    searchParams = new URLSearchParams("page_size=all");
    afficher({ total: 3, pageSize: null });

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/ }));

    expect(screen.getByRole("status").textContent).not.toContain("lignes affichées");
  });

  it("porte le périmètre jusque dans l'aria-label des en-têtes", () => {
    afficher({ total: 860, pageSize: 20 });

    expect(
      screen.getByRole("button", { name: "Trier par temps total, croissant, sur les 3 lignes affichées" }),
    ).toBeInTheDocument();
  });

  it("accorde le périmètre au singulier quand une seule ligne est affichée", async () => {
    afficher({ participations: [data[0]], total: 860, pageSize: 20 });

    expect(
      screen.getByRole("button", { name: "Trier par temps total, croissant, sur la ligne affichée" }),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/ }));

    expect(screen.getByRole("status").textContent).toContain("sur la ligne affichée");
  });

  it("ne mentionne aucun périmètre quand le tri porte sur zéro ligne affichée (#M3)", async () => {
    searchParams = new URLSearchParams("q=zzz");
    afficher({ participations: [], total: 0 });

    // Le périmètre de tri se lit dans l'aria-label avant même de cliquer :
    // il décrit la prochaine direction, « 0 lignes affichées » n'a rien à dire.
    expect(
      screen.getByRole("button", { name: "Trier par temps total, croissant" }),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Trier par temps total/ }));

    expect(screen.getByRole("status").textContent).not.toContain("lignes affichées");
  });

  // ── Cible tactile (#479) ────────────────────────────────────────────────────

  it("porte l'en-tête triable à la taille tactile minimale (24 px)", () => {
    // WCAG 2.2 2.5.8 : 24 px CSS minimum. `padding: 0` sur un texte de 11 px
    // ne laissait qu'une bande de ~11 px cliquable.
    afficher();

    const entete = screen.getByRole("button", { name: /trier par temps total/i });
    expect(Number.parseInt(entete.style.minHeight, 10)).toBeGreaterThanOrEqual(24);
  });

  it("centre verticalement la ligne d'en-tête, comme la ligne de résultat (revue de code)", () => {
    // Le bouton triable impose maintenant `minHeight: 24`, plus haut que le
    // texte brut des autres cellules ("Rang", "Athlète"…) : sans
    // `alignItems: "center"` sur la ligne, la grille les étire (`stretch`,
    // le défaut) et leur texte remonte en haut de la ligne pendant que le
    // bouton reste centré sur lui-même.
    afficher();

    const ligne = screen.getByText("Rang").parentElement;
    expect(ligne).toHaveStyle({ alignItems: "center" });
  });

  // ── Cadre de la vue filtrée (RES-9) ────────────────────────────────────────

  it("oppose le total de la sélection à celui de l'épreuve après une recherche", () => {
    searchParams = new URLSearchParams("q=kermarrec");
    afficher({ summary: synthese({ total: 498 }), total: 2 });

    expect(screen.getByText(/2 résultats/)).toBeInTheDocument();
    expect(screen.getByText(/sur 498/)).toBeInTheDocument();
    expect(screen.getByText(/kermarrec/)).toBeInTheDocument();
  });

  it("sépare recherche et filtre club par un espace, pas une virgule (#485 re-revue)", () => {
    // Verrouille la copie exacte du seul cas qui combine les deux clauses :
    // les autres tests de cette section n'assertent que des fragments et
    // ne distinguent pas join(" ") de join(", ").
    searchParams = new URLSearchParams(`q=kermarrec&${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ summary: synthese({ total: 498, tcn_count: 12 }), total: 2 });

    expect(
      screen.getByText(
        "2 résultats sur 498 pour « kermarrec » du Triathlon Club Nantais",
      ),
    ).toBeInTheDocument();
  });

  it("nomme le filtre club dans la ligne d'état", () => {
    searchParams = new URLSearchParams(`${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ summary: synthese({ total: 498, tcn_count: 12 }), total: 12 });

    expect(screen.getByText(/du Triathlon Club Nantais/)).toBeInTheDocument();
  });

  it("ne rend aucune ligne d'état en vue complète", () => {
    afficher({ total: 3 });

    expect(screen.queryByRole("button", { name: "Effacer" })).not.toBeInTheDocument();
  });

  it("« Tout effacer » retire les quatre restrictions d'un coup", async () => {
    // Renommé avec #486 : quatre filtres peuvent coexister, chacun avec son
    // propre repère retirable, et « Effacer » seul ne disait plus quoi.
    searchParams = new URLSearchParams(`q=kermarrec&${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ summary: synthese({ total: 498 }), total: 1 });

    await userEvent.click(screen.getByRole("button", { name: "Tout effacer" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("situe le pied de carte sur l'épreuve entière, pas sur la sélection", () => {
    searchParams = new URLSearchParams("q=kermarrec");
    afficher({ total: 2 });

    expect(screen.getByText(/Sur l'ensemble de l'épreuve/)).toBeInTheDocument();
  });

  it("grise l'onglet club quand l'épreuve ne compte aucun athlète TCN", () => {
    afficher({ summary: synthese({ total: 498, tcn_count: 0 }) });

    expect(screen.getByRole("button", { name: /Triathlon Club Nantais \(0\)/ })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  it("laisse l'onglet club actif dès qu'un athlète TCN figure sur l'épreuve", () => {
    afficher({ summary: synthese({ total: 498, tcn_count: 3 }) });

    expect(screen.getByRole("button", { name: /Triathlon Club Nantais \(3\)/ })).not.toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  // ── Structure de tableau (#481, A11Y-3) ────────────────────────────────────
  //
  // Le classement était une grille de `div` dont l'en-tête n'était reliée à
  // rien : un lecteur d'écran énonçait « 01:10:47 » sans jamais dire de quelle
  // colonne. Ces tests interrogent l'arbre d'accessibilité, jamais le nom des
  // balises — c'est ce qui laisse la mise en œuvre libre (contrat C1/C2).

  it("s'annonce comme un tableau nommé, une ligne d'en-tête plus une par participant", () => {
    // Nommé, parce que `/courses/[id]` en porte deux : sans nom, un lecteur
    // d'écran annonce « tableau » deux fois sans dire lequel (revue de code
    // #481 — « Top clubs » l'était, celui-ci ne l'était pas).
    afficher();

    expect(screen.getByRole("table", { name: "Classement" })).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(1 + data.length);
  });

  it("nomme chacune de ses colonnes, inters de la synthèse compris", () => {
    afficher({
      summary: synthese({ split_keys: ["swim", "bike", "run"] }),
      eventType: "triathlon-m",
    });

    for (const nom of ["Rang", "Athlète", "Catég.", "Sexe", "Temps total", "Club"]) {
      expect(screen.getByRole("columnheader", { name: nom })).toBeInTheDocument();
    }
    for (const inter of ["Natation", "Vélo", "Course"]) {
      expect(screen.getByRole("columnheader", { name: new RegExp(inter) })).toBeInTheDocument();
    }
  });

  it("range chaque valeur dans la cellule de sa colonne", () => {
    afficher({
      participations: [
        p({ id: 9, nom: "KERMARREC", rank_overall: 4, total_time: "01:10:47", club: "TCN" }),
      ],
      total: 1,
    });

    // L'ordre des cellules est le contrat : c'est lui qui rattache une valeur à
    // son en-tête. Rang, Athlète, Catég., Sexe, Temps total, Club.
    const cellules = within(screen.getAllByRole("row")[1]).getAllByRole("cell");
    expect(cellules).toHaveLength(6);
    expect(cellules[1]).toHaveTextContent("KERMARREC");
    expect(cellules[2]).toHaveTextContent("S4");
    expect(cellules[4]).toHaveTextContent("01:10:47");
    expect(cellules[5]).toHaveTextContent("TCN");
  });

  it("annonce la direction du tri sur la colonne triée, et « none » sur les autres colonnes triables", async () => {
    // `aria-sort` dit l'**état** ; l'`aria-label` du bouton dit l'action à
    // venir. Les deux sont complémentaires, et c'est le premier qui manquait.
    const user = userEvent.setup();
    afficher({
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    const tempsTotal = screen.getByRole("columnheader", { name: /Temps total/ });
    const natation = screen.getByRole("columnheader", { name: /Natation/ });
    expect(tempsTotal).toHaveAttribute("aria-sort", "none");
    expect(natation).toHaveAttribute("aria-sort", "none");

    await user.click(within(tempsTotal).getByRole("button"));
    expect(tempsTotal).toHaveAttribute("aria-sort", "ascending");
    expect(natation).toHaveAttribute("aria-sort", "none");

    await user.click(within(tempsTotal).getByRole("button"));
    expect(tempsTotal).toHaveAttribute("aria-sort", "descending");
  });

  it("ne porte aucun aria-sort sur les colonnes qui ne se trient pas", () => {
    afficher();

    for (const nom of ["Rang", "Athlète", "Catég.", "Sexe", "Club"]) {
      expect(screen.getByRole("columnheader", { name: nom })).not.toHaveAttribute("aria-sort");
    }
  });

  it("garde son en-tête sur une épreuve vide, et laisse l'état vide hors du tableau", () => {
    // FR-007 : l'en-tête est rendue aujourd'hui sur une liste vide, elle doit
    // continuer de l'être. L'`EmptyState` reste un frère du tableau — le poser
    // en ligne le ferait annoncer comme une donnée du classement.
    afficher({ participations: [], total: 0 });

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(1);
    expect(
      within(screen.getByRole("table")).queryByText("Aucun participant à afficher"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Aucun participant à afficher")).toBeInTheDocument();
  });
});

describe("RaceFinishers — ma ligne dans le classement (NAV-10, #503)", () => {
  // Restauré en `afterEach` : sans lui, le prochain `describe` hériterait en
  // silence de ce faux `localStorage`.
  const descripteurOriginal = Object.getOwnPropertyDescriptor(window, "localStorage")!;

  beforeEach(() => {
    const stock = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (cle: string) => stock.get(cle) ?? null,
        setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
        removeItem: (cle: string) => void stock.delete(cle),
        clear: () => stock.clear(),
      },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "localStorage", descripteurOriginal);
  });

  it("ne marque aucune ligne quand aucun athlète n'est retenu", () => {
    afficher();
    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
  });

  it("marque la seule ligne de l'athlète retenu, d'un chip et non de la couleur seule", () => {
    // `p({ id, nom })` donne `athlete.id === id` : l'athlète retenu est donc
    // celui de la ligne 3 (DNFGUY) — un abandon reste ma ligne.
    writeAthlete({ id: 3, prenom: "T", nom: "DNFGUY" });
    afficher();

    // Scopé à la grille : depuis #461, la même ligne existe aussi dans
    // l'arbre carte (masqué par CSS, toujours dans le DOM).
    const marques = within(screen.getByTestId("classement-grille")).getAllByText("Vous");
    expect(marques).toHaveLength(1);
    // WCAG 1.4.1 : le chip est le signifiant, le fond ne fait que l'appuyer.
    expect(marques[0].closest("tr")).toHaveTextContent("DNFGUY");
  });

  it("marque aussi ma ligne d'un chip « Vous » dans l'arbre carte (revue finale #461)", () => {
    // Régression relevée en revue finale : la boucle des cartes ne lisait
    // jamais `moi`, donc sur téléphone rien ne distinguait ma ligne — alors
    // que « Aller à ma ligne » y reste offert.
    writeAthlete({ id: 3, prenom: "T", nom: "DNFGUY" });
    afficher();

    expect(dansLesCartes("classement-cartes").texte("Vous")).toBeInTheDocument();
  });

  it("peint le fond de ma ligne, y compris sur un non-finisher — par une classe, pas un style en ligne", () => {
    // Le fond vit en CSS (`.tcn-rowlink--moi`, globals.css) : un style en
    // ligne battrait `.tcn-rowlink:hover` et couperait le retour au survol
    // (#439, correctif de revue #503).
    writeAthlete({ id: 3, prenom: "T", nom: "DNFGUY" });
    afficher();

    const ligne = screen.getByText("Vous").closest("tr") as HTMLElement;
    expect(ligne.className).toMatch(/(^|\s)tcn-rowlink--moi(\s|$)/);
    expect(ligne.style.background).toBe("");
  });

  it("ne porte la classe modificatrice que sur ma ligne, pas sur les autres", () => {
    writeAthlete({ id: 3, prenom: "T", nom: "DNFGUY" });
    afficher();

    const lignes = screen
      .getAllByRole("link", { name: /Voir le détail du résultat de/ })
      .map((lien) => lien.closest("tr") as HTMLElement);
    const autres = lignes.filter((ligne) => !ligne.textContent?.includes("DNFGUY"));
    expect(autres.length).toBeGreaterThan(0);
    for (const ligne of autres) {
      expect(ligne.className).not.toMatch(/(^|\s)tcn-rowlink--moi(\s|$)/);
    }
  });

  it("n'offre pas le saut quand aucun athlète n'est retenu", () => {
    afficher();
    expect(screen.queryByRole("button", { name: /Aller à ma ligne/ })).not.toBeInTheDocument();
  });

  it("cherche mon nom complet dans le classement, page courante indifférente", async () => {
    writeAthlete({ id: 3, prenom: "Thomas", nom: "DNFGUY" });
    searchParams = new URLSearchParams("page=4");
    afficher({ page: 4 });

    await userEvent.click(screen.getByRole("button", { name: "Aller à ma ligne — Thomas DNFGUY" }));

    // La recherche remet à la page 1 : `naviguer` retire `page`.
    expect(push).toHaveBeenCalledWith("/courses/1?q=Thomas+DNFGUY");
  });

  it("nomme l'athlète quand il ne figure pas sur l'épreuve, plutôt qu'un échec de recherche", async () => {
    writeAthlete({ id: 99, prenom: "Marie", nom: "GAUDIN" });
    searchParams = new URLSearchParams("q=Marie GAUDIN");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText("Marie GAUDIN ne figure pas sur cette épreuve")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voir tous les participants" }));
    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("garde l'état vide générique pour une recherche qui n'est pas la mienne", () => {
    writeAthlete({ id: 99, prenom: "Marie", nom: "GAUDIN" });
    searchParams = new URLSearchParams("q=zzz");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText("Aucun athlète ne correspond à cette recherche")).toBeInTheDocument();
  });

  it("retire la portée club en même temps qu'il pose la recherche, sinon le saut peut ne pas mener à ma ligne", async () => {
    writeAthlete({ id: 3, prenom: "Thomas", nom: "DNFGUY" });
    searchParams = new URLSearchParams(SCOPE_PARAM + "=" + SCOPE_CLUB);
    afficher();

    await userEvent.click(screen.getByRole("button", { name: "Aller à ma ligne — Thomas DNFGUY" }));

    const url = push.mock.calls.at(-1)?.[0] ?? "";
    expect(url).not.toContain(SCOPE_PARAM);
    expect(url).toContain("q=Thomas+DNFGUY");
  });

  it("« Voir tous les participants » de l'état « ne figure pas » ramène à l'épreuve nue, portée club retirée", async () => {
    writeAthlete({ id: 99, prenom: "Marie", nom: "GAUDIN" });
    searchParams = new URLSearchParams(`q=Marie GAUDIN&${SCOPE_PARAM}=${SCOPE_CLUB}`);
    afficher({ participations: [], total: 0 });

    expect(screen.getByText("Marie GAUDIN ne figure pas sur cette épreuve")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voir tous les participants" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });
});

// ── Marqueur d'écart des inters (#486, RES-10) ──────────────────────────────
//
// Les seuils viennent du sondage
// `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`, qui prime :
// celui de 2 % proposé par l'audit signalait 8,02 % du classement, dont 285
// lignes d'une épreuve saine. Une ligne n'est douteuse que face à **ses pairs**.

describe("RaceFinishers — marqueur d'écart", () => {
  const MARQUEUR = { name: /ne rendent pas compte/i };

  function afficherEcart(participations: Participation[], over: Partial<CourseSummary>) {
    return render(
      <RaceFinishers
        participations={participations}
        summary={synthese(over)}
        total={participations.length}
        page={1}
        pageSize={20}
      />,
    );
  }

  const ligne = (ratio: number | null, total = "01:00:00") =>
    p({
      id: 1,
      nom: "ECART",
      status: "finisher",
      rank_overall: 1,
      total_time: total,
      split_gap_ratio: ratio,
    });

  it("marque une ligne qui s'écarte de plus de 5 % de la médiane de son épreuve", () => {
    afficherEcart([ligne(0.2)], { split_gap_median: 0, split_gap_rows: 100 });

    expect(screen.getByRole("img", MARQUEUR)).toBeInTheDocument();
  });

  it("ne marque pas une ligne alignée sur ses pairs, même à fort écart absolu", () => {
    // Course 66 : 100 % des lignes à +7,44 %. Ce n'est pas la ligne qui est
    // fausse, c'est la transition que le chronométreur ne publie pas.
    afficherEcart([ligne(0.0744)], { split_gap_median: 0.0744, split_gap_rows: 13 });

    expect(screen.queryByRole("img", MARQUEUR)).not.toBeInTheDocument();
  });

  it("ne marque rien sous dix lignes évaluables — la médiane n'y est pas une référence", () => {
    afficherEcart([ligne(0.2)], { split_gap_median: 0, split_gap_rows: 9 });

    expect(screen.queryByRole("img", MARQUEUR)).not.toBeInTheDocument();
  });

  it("ne marque rien sous soixante secondes d'écart, quel que soit le pourcentage", () => {
    // 10 % d'un total de 5 minutes = 30 s : au-dessus du seuil relatif, sous le
    // plancher absolu. Sans lui, un petit dénominateur suffit à franchir 5 %.
    afficherEcart([ligne(0.1, "00:05:00")], { split_gap_median: 0, split_gap_rows: 50 });

    expect(screen.queryByRole("img", MARQUEUR)).not.toBeInTheDocument();
  });

  it("ne marque rien quand l'épreuve n'a pas de médiane", () => {
    afficherEcart([ligne(0.5)], { split_gap_median: null, split_gap_rows: 0 });

    expect(screen.queryByRole("img", MARQUEUR)).not.toBeInTheDocument();
  });

  it("rend les temps publiés tels quels, marqueur ou non (FR-009)", () => {
    // Le marqueur informe, il ne réécrit pas la donnée : ni correction, ni
    // masquage, ni recalcul du total à partir des inters.
    const kermarrec = p({
      id: 1,
      nom: "ECART",
      status: "finisher",
      rank_overall: 1,
      total_time: "01:06:18",
      splits: { swim: "00:00:31" },
      split_gap_ratio: 0.693,
    });
    afficherEcart([kermarrec], {
      split_gap_median: 0,
      split_gap_rows: 498,
      split_keys: ["swim"],
    });

    expect(screen.getByRole("img", MARQUEUR)).toBeInTheDocument();
    expect(screen.getByText("01:06:18")).toBeInTheDocument();
    expect(screen.getByText("00:00:31")).toBeInTheDocument();
  });
});

// ── Repères des filtres de carte (#486, RES-11) ─────────────────────────────

describe("RaceFinishers — filtres club et catégorie", () => {
  it("porte un repère par filtre actif, retirable indépendamment", () => {
    // Retirer les deux d'un bloc effacerait le club qu'on venait de choisir en
    // activant une catégorie depuis la carte voisine (FR-021).
    searchParams = new URLSearchParams("club=BLAIN+TRIATHLON&category=V2");
    afficher({ participations: [], total: 0 });

    expect(
      screen.getByRole("button", { name: 'Retirer le filtre club « BLAIN TRIATHLON »' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Retirer le filtre catégorie/ }),
    ).toBeInTheDocument();
  });

  it("donne au repère de catégorie son libellé complet", () => {
    searchParams = new URLSearchParams("category=V2");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText("V2 — Vétéran 2")).toBeInTheDocument();
  });

  it("annonce la sélection face au total de l'épreuve", () => {
    searchParams = new URLSearchParams("club=BLAIN+TRIATHLON");
    afficher({ participations: [data[0]], total: 33, summary: synthese({ total: 498 }) });

    expect(screen.getByText(/33 résultats sur 498/)).toBeInTheDocument();
  });

  it("nomme le filtre en cause quand la sélection est vide, sans parler de recherche", () => {
    // Défaut constaté sur `/courses/340?scope=club` : « Aucun athlète ne
    // correspond à cette recherche » alors qu'aucune recherche n'a été faite.
    searchParams = new URLSearchParams("club=CLUB+INEXISTANT");
    afficher({ participations: [], total: 0 });

    const absence = screen.getByText(/du club « CLUB INEXISTANT »/);
    expect(absence).toBeInTheDocument();
    // Le mot « recherche » ne doit pas apparaître **dans l'état d'absence** —
    // le champ de recherche, lui, reste monté au-dessus.
    expect(absence.textContent).not.toMatch(/recherche/i);
  });

  it("nomme le filtre de carte même quand une recherche est active", () => {
    // Sinon la branche « recherche » gagne, l'écran dit « Aucun athlète ne
    // correspond à cette recherche », et « Effacer la recherche » laisse le
    // visiteur sur un écran toujours vide sans jamais nommer ce qui le vidait.
    searchParams = new URLSearchParams("q=dupont&club=CLUB+INEXISTANT");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText(/du club « CLUB INEXISTANT »/)).toBeInTheDocument();
    expect(
      screen.queryByText("Aucun athlète ne correspond à cette recherche"),
    ).not.toBeInTheDocument();
  });

  it("efface la recherche en même temps que le filtre de carte", async () => {
    searchParams = new URLSearchParams("q=dupont&club=CLUB+INEXISTANT");
    afficher({ participations: [], total: 0 });

    await userEvent.click(screen.getByRole("button", { name: "Voir tous les participants" }));

    expect(push).toHaveBeenCalledWith("/courses/1");
  });

  it("explique le croisement vide par construction avec la portée TCN", () => {
    searchParams = new URLSearchParams("club=BLAIN+TRIATHLON&scope=club");
    afficher({ participations: [], total: 0 });

    expect(screen.getByText(/s'excluent/)).toBeInTheDocument();
  });

  it("nomme les filtres actifs dans l'annonce, pas seulement le décompte", () => {
    // Deux filtres différents peuvent rendre le même nombre de lignes : le
    // décompte seul ne dirait alors rien avoir changé (FR-032).
    searchParams = new URLSearchParams("club=BLAIN+TRIATHLON&category=V2");
    afficher();

    const annonce = screen.getByRole("status").textContent ?? "";
    expect(annonce).toContain("du club BLAIN TRIATHLON");
    expect(annonce).toContain("en catégorie V2 — Vétéran 2");
  });

  it("ne montre aucun repère quand aucun filtre de carte n'est actif", () => {
    searchParams = new URLSearchParams("");
    afficher();

    expect(screen.queryByRole("button", { name: /Retirer le filtre/ })).not.toBeInTheDocument();
  });
});

describe("rendu carte sous lg", () => {
  const cartes = () => dansLesCartes("classement-cartes");
  const grille = () => screen.getByTestId("classement-grille");

  it("bascule la grille et les cartes aux seuils annoncés", () => {
    render(
      <RaceFinishers
        participations={[p({ id: 1, nom: "DUPONT", rank_overall: 1, total_time: "01:04:12" })]}
        summary={synthese()}
        total={1}
        page={1}
        pageSize={20}
      />,
    );
    expect(grille().className).toContain("hidden min-[1237px]:block");
    expect(screen.getByTestId("classement-cartes").className).toContain("min-[1237px]:hidden");
  });

  it("porte place, nom, temps et méta dans la carte", () => {
    render(
      <RaceFinishers
        participations={[
          p({ id: 1, nom: "DUPONT", rank_overall: 1, total_time: "01:04:12", club: "TCN", is_tcn: true }),
        ]}
        summary={synthese()}
        total={1}
        page={1}
        pageSize={20}
      />,
    );
    const carte = cartes();
    expect(carte.texte("DUPONT T")).toBeInTheDocument();
    expect(carte.texte("01:04:12")).toBeInTheDocument();
    expect(carte.texte("1")).toBeInTheDocument();
    // La méta est une seule chaîne « club · catégorie · sexe ».
    expect(carte.texte(/TCN · S4/)).toBeInTheDocument();
  });

  it("n'affiche aucune méta quand club, catégorie et sexe sont tous absents, plutôt que trois tirets accolés (revue finale #461)", () => {
    // Le `.filter(Boolean)` de la méta portait sur des valeurs déjà repliées
    // (« — », et `genderShort(null)` qui vaut lui-même « — ») : il ne
    // retirait donc jamais rien, et affichait « — · — · — » là où la grille
    // répartit trois tirets dans trois colonnes distinctes, ce qui se lit.
    render(
      <RaceFinishers
        participations={[
          {
            ...p({ id: 1, nom: "DUPONT", rank_overall: 1, total_time: "01:04:12" }),
            club: null,
            category: null,
            athlete: { id: 1, nom: "DUPONT", prenom: "T", gender: "", club: null },
          },
        ]}
        summary={synthese()}
        total={1}
        page={1}
        pageSize={20}
      />,
    );
    // `textContent` brut, pas une requête texte : la carte est exclue des
    // requêtes texte par `test/setup.ts`, et c'est une absence qu'on vérifie
    // ici — `dansLesCartes` ne porte pas de pendant négatif à `.texte()`.
    const carte = screen.getByTestId("classement-cartes");
    expect(carte.textContent).not.toMatch(/—/);
  });

  it("range les inters dans un dépliant, ⚠ compris", () => {
    render(
      <RaceFinishers
        participations={[
          p({ id: 1, nom: "DUPONT", rank_overall: 1, total_time: "01:04:12", splits: { swim: "0-2:-15:00" } }),
        ]}
        summary={synthese({ split_keys: ["swim"] })}
        total={1}
        page={1}
        pageSize={20}
        eventType="triathlon"
      />,
    );
    const carte = cartes();
    expect(carte.texte("Inters")).toBeInTheDocument();
    // `getByRole` n'est pas concerné par `defaultIgnore`, mais reste scopé aux
    // cartes : le même ⚠ existe dans l'arbre grille.
    expect(carte.getByRole("img", { name: /illisible/i })).toBeInTheDocument();
  });

  // Trois lignes, dans un ordre backend qui n'est ni croissant ni décroissant :
  // avec deux lignes, « décroissant » redonnerait l'ordre de départ et le test
  // ne prouverait rien.
  it("trie depuis le contrôle mobile, et la grille suit", async () => {
    render(
      <RaceFinishers
        participations={[
          p({ id: 1, nom: "MOYEN", rank_overall: 1, total_time: "01:30:00" }),
          p({ id: 2, nom: "LENT", rank_overall: 2, total_time: "02:00:00" }),
          p({ id: 3, nom: "RAPIDE", rank_overall: 3, total_time: "01:00:00" }),
        ]}
        summary={synthese()}
        total={3}
        page={1}
        pageSize={20}
      />,
    );
    const noms = () =>
      within(grille())
        .getAllByText(/^(MOYEN|LENT|RAPIDE) T$/)
        .map((n) => n.textContent);

    // L'ordre du backend d'abord : la vue n'est pas triée.
    expect(noms()).toEqual(["MOYEN T", "LENT T", "RAPIDE T"]);

    const bouton = cartes().getByRole("button", { name: /Inverser l'ordre/ });
    expect(bouton).toHaveAccessibleName(/actuellement croissant/);

    await userEvent.click(bouton);

    // Le contrôle mobile écrit dans le même état `tri` que les en-têtes :
    // l'arbre grille est réordonné lui aussi. Premier appui = décroissant, ce
    // que le nom accessible du bouton annonçait (« actuellement croissant »).
    expect(noms()).toEqual(["LENT T", "MOYEN T", "RAPIDE T"]);
    // Le nom accessible reste accordé à l'état réel après l'appui : un
    // lecteur d'écran n'a que lui pour savoir dans quel sens ira le suivant.
    expect(bouton).toHaveAccessibleName(/actuellement décroissant/);
  });

  it("ne bascule pas la direction quand on rechoisit depuis le sélecteur la colonne déjà active", async () => {
    // `choisirTri` existe précisément pour ça, à la différence de `trierSur` :
    // rechoisir dans une liste déroulante la valeur déjà active n'est pas un
    // geste d'inversion — sinon rouvrir le menu et reconfirmer « Temps total »
    // inverserait le tri à chaque fois qu'on referme le menu.
    render(
      <RaceFinishers
        participations={[
          p({ id: 1, nom: "MOYEN", rank_overall: 1, total_time: "01:30:00" }),
          p({ id: 2, nom: "LENT", rank_overall: 2, total_time: "02:00:00" }),
          p({ id: 3, nom: "RAPIDE", rank_overall: 3, total_time: "01:00:00" }),
        ]}
        summary={synthese()}
        total={3}
        page={1}
        pageSize={20}
      />,
    );
    const noms = () =>
      within(grille())
        .getAllByText(/^(MOYEN|LENT|RAPIDE) T$/)
        .map((n) => n.textContent);

    // Le tri est d'abord posé sur « Temps total », décroissant, par le bouton
    // d'inversion — seul moyen d'obtenir un tri non `null` sur cette colonne.
    await userEvent.click(cartes().getByRole("button", { name: /Inverser l'ordre/ }));
    expect(noms()).toEqual(["LENT T", "MOYEN T", "RAPIDE T"]);

    await userEvent.click(cartes().getByRole("combobox", { name: /Trier par/i }));
    // Le menu se rend dans un portail, hors de `classement-cartes` : requête
    // non scopée, comme `EventsTable.test.tsx` pour le même composant `Select`.
    await userEvent.click(await screen.findByRole("option", { name: "Temps total" }));

    // « Temps total » était déjà la colonne active : la reconfirmer garde la
    // direction décroissante en cours. `trierSur` l'aurait inversée en
    // croissant (["RAPIDE T", "MOYEN T", "LENT T"]) ; `choisirTri` ne le fait pas.
    expect(noms()).toEqual(["LENT T", "MOYEN T", "RAPIDE T"]);
  });
});
