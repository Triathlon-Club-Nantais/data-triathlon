// frontend/components/results/RaceFinishers.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { StrictMode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CourseSummary, Participation } from "@/lib/types";
import { SCOPE_CLUB, SCOPE_PARAM } from "@/lib/scope";

const push = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/courses/1",
  useSearchParams: () => searchParams,
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
    histogram: null,
    split_keys: [],
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
    afficher({ total: 100, pageSize: 20, page: 4 });

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

  it("efface la recherche et le filtre club quand rien ne correspond (revue de code #476)", async () => {
    searchParams = new URLSearchParams("q=zzz&" + SCOPE_PARAM + "=" + SCOPE_CLUB);
    afficher({ participations: [], total: 0 });

    await userEvent.click(screen.getByRole("button", { name: "Effacer la recherche" }));

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

  it("signale l'inter illisible au lieu de le taire, et rappelle la valeur reçue", () => {
    // Masquer sans rien dire ferait croire que le chronométreur n'a rien publié.
    afficherInter();
    expect(screen.getByRole("img", { name: /illisible/i })).toHaveAccessibleName(
      new RegExp(ILLISIBLE),
    );
  });

  it("laisse un inter absent en simple tiret, sans signal", () => {
    afficherInter({});
    expect(screen.queryByRole("img", { name: /illisible/i })).not.toBeInTheDocument();
  });

  it("rend tel quel un inter parsable", () => {
    afficherInter({ swim: "00:25:00" });
    expect(screen.getByText("00:25:00")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /illisible/i })).not.toBeInTheDocument();
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

  it("ouvre le détail de la participation, et non plus le profil de l'athlète", async () => {
    const user = userEvent.setup();
    afficher();

    await user.click(screen.getByText("FINISHER T"));

    expect(push).toHaveBeenCalledWith("/courses/1/participations/1");
  });

  it("ouvre le même détail au clavier", async () => {
    const user = userEvent.setup();
    afficher();

    screen.getByText("FINISHER T").closest<HTMLElement>("[role=button]")?.focus();
    await user.keyboard("{Enter}");

    expect(push).toHaveBeenCalledWith("/courses/1/participations/1");
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
});
