// frontend/components/results/RaceFinishers.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { StrictMode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CourseSummary, Participation } from "@/lib/types";

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

  it("ventile le pied de tableau : partants · finishers · abandons (pas « X finishers au total »)", () => {
    afficher();
    expect(screen.getByText("3 partants · 1 finisher · 2 abandons")).toBeInTheDocument();
  });

  it("ajoute les « indéterminés » au pied de tableau pour réconcilier avec le total", () => {
    afficher({ summary: synthese({ total: 4, finishers: 1, non_finishers: 1, unknown: 2 }) });
    expect(
      screen.getByText("4 partants · 1 finisher · 1 abandon · 2 indéterminés"),
    ).toBeInTheDocument();
  });

  it("prend son décompte dans la synthèse, pas dans la page affichée", () => {
    // Une page de 3 lignes sur une épreuve de 1811 : le pied annonce l'épreuve.
    afficher({ summary: synthese({ total: 1811, finishers: 1768, non_finishers: 43 }), total: 1811 });
    expect(screen.getByText(/1811 partants/)).toBeInTheDocument();
  });

  // ── Pagination ─────────────────────────────────────────────────────────────

  it("ne rend aucun contrôle de pagination quand la sélection tient en une page", () => {
    afficher({ total: 3, pageSize: 20 });
    expect(screen.queryByRole("navigation", { name: /pagination/i })).not.toBeInTheDocument();
  });

  it("rend des liens « Précédent » / « Suivant » portant le numéro de page", () => {
    afficher({ total: 100, pageSize: 20, page: 3 });

    expect(screen.getByText("Page 3 sur 5")).toBeInTheDocument();
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

  it("bascule le filtre club en paramètre d'URL et revient à la première page", async () => {
    searchParams = new URLSearchParams("page=4");
    afficher({ total: 100, pageSize: 20, page: 4 });

    await userEvent.click(screen.getByRole("button", { name: /Triathlon Club Nantais/ }));

    expect(push).toHaveBeenCalledWith("/courses/1?scope=club");
  });

  it("propose le retour au début sur une page hors bornes, plutôt qu'un cul-de-sac", () => {
    searchParams = new URLSearchParams("page=99999");
    afficher({ participations: [], total: 100, pageSize: 20, page: 99999 });

    expect(screen.getByText(/Cette page n'existe pas/)).toBeInTheDocument();
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
    expect(screen.getByText(/Aucun athlète ne correspond/)).toBeInTheDocument();
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

  it("en-tête de split activable au clavier, avec libellé français explicite", () => {
    afficher({
      participations: dataAvecSplits,
      summary: synthese({ split_keys: ["swim"] }),
      eventType: "triathlon-m",
    });

    const bouton = screen.getByRole("button", { name: /Trier par temps.*Natation/i });
    expect(bouton.tagName).toBe("BUTTON");
  });
});
