// frontend/components/results/RaceFinishers.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
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

  it("resynchronise le champ de recherche quand l'URL change (retour navigateur)", () => {
    searchParams = new URLSearchParams("q=dupont");
    const { rerender } = afficher();
    expect(screen.getByRole("searchbox")).toHaveValue("dupont");

    searchParams = new URLSearchParams();
    rerender(
      <RaceFinishers participations={data} summary={synthese()} total={3} page={1} pageSize={20} />,
    );
    expect(screen.getByRole("searchbox")).toHaveValue("");
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
});
