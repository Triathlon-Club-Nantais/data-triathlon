import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Participation } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { PodiumsList, APERCU_PODIUMS } from "./PodiumsList";

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

const PARTS: Participation[] = [
  part({ id: 1, rank_overall: 30, rank_category: 1 }), // podium cat seul
  part({ id: 2, rank_overall: 2 }), // podium scratch seul
  part({ id: 3, rank_gender: 1 }), // podium genre seul
];

describe("PodiumsList — filtrage selon ?rank= (#104, #132)", () => {
  it("sans ?rank= (défaut scratch) : n'affiche que les badges « Général »", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByText("Général")).toBeInTheDocument();
    expect(screen.queryByText("Catégorie")).not.toBeInTheDocument();
    expect(screen.queryByText("Genre")).not.toBeInTheDocument();
  });

  it("?rank=category : n'affiche que les badges « Catégorie »", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByText("Catégorie")).toBeInTheDocument();
    expect(screen.queryByText("Général")).not.toBeInTheDocument();
    expect(screen.queryByText("Genre")).not.toBeInTheDocument();
  });

  it("?rank=gender : n'affiche que les badges « Genre »", () => {
    searchParams = new URLSearchParams("rank=gender");
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByText("Genre")).toBeInTheDocument();
    expect(screen.queryByText("Général")).not.toBeInTheDocument();
    expect(screen.queryByText("Catégorie")).not.toBeInTheDocument();
  });

  it("?rank=all : montre le mélange des trois scopes (comportement historique)", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByText("Général")).toBeInTheDocument();
    expect(screen.getByText("Catégorie")).toBeInTheDocument();
    expect(screen.getByText("Genre")).toBeInTheDocument();
  });

  it("liste vide → message d'attente, aucun badge", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={[]} />);
    expect(screen.getByText("Pas encore de podium enregistré.")).toBeInTheDocument();
  });
});

describe("PodiumsList — icône par scope (#128)", () => {
  it("?rank=all : chaque scope porte une icône avec aria-label distinct", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByLabelText("Podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("Podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("Podium de genre")).toBeInTheDocument();
  });

  it("?rank=category (mode unique) : seule l'icône de catégorie apparaît", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByLabelText("Podium de catégorie")).toBeInTheDocument();
    expect(screen.queryByLabelText("Podium général")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Podium de genre")).not.toBeInTheDocument();
  });

  it("chaque icône porte un tooltip natif (`title`) explicite au survol", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByLabelText("Podium général")).toHaveAttribute(
      "title",
      "Podium général (top 3 scratch)",
    );
    expect(screen.getByLabelText("Podium de catégorie")).toHaveAttribute(
      "title",
      "Podium de catégorie (top 3 dans sa catégorie d'âge)",
    );
    expect(screen.getByLabelText("Podium de genre")).toHaveAttribute(
      "title",
      "Podium de genre (top 3 dans son sexe)",
    );
  });
});

// WCAG 4.1.3 (#477) : `?rank=` recalcule en mémoire (#132), sans navigation.
describe("PodiumsList — annonce du changement (#477)", () => {
  it("annonce le nombre de podiums affichés dans une région role=status", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={PARTS} />);
    expect(screen.getByRole("status")).toHaveTextContent("1 podium affiché");
  });

  it("réannonce au changement de mode", () => {
    searchParams = new URLSearchParams();
    const { rerender } = render(<PodiumsList participations={PARTS} />);

    searchParams = new URLSearchParams("rank=all");
    rerender(<PodiumsList participations={PARTS} />);

    expect(screen.getByRole("status")).toHaveTextContent("3 podiums affichés");
  });

  it("reste montée et annonce zéro quand la bascule ne laisse plus aucun podium (revue de code)", () => {
    // Avant la revue : la région `role="status"` était rendue APRÈS le retour
    // anticipé sur liste vide, donc elle disparaissait du DOM au moment précis
    // où un lecteur d'écran aurait le plus besoin d'être prévenu.
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={[]} />);

    expect(screen.getByRole("status")).toHaveTextContent("0 podium affiché");
  });
});

describe("PodiumsList — extension de la liste (PROF-3, #488)", () => {
  // 9 podiums scratch : au-delà de l'aperçu, donc 3 restants.
  const NEUF = Array.from({ length: 9 }, (_, i) => part({ id: i + 1, rank_overall: 1 }));

  it("n'offre pas d'extension quand tout tient dans l'aperçu", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={NEUF.slice(0, APERCU_PODIUMS)} />);

    expect(screen.queryByRole("button", { name: /Voir les/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(APERCU_PODIUMS);
  });

  it("dit combien de podiums restent sous l'aperçu", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={NEUF} />);

    expect(screen.getAllByRole("listitem")).toHaveLength(APERCU_PODIUMS);
    expect(screen.getByRole("button", { name: "Voir les 3 autres podiums" })).toBeInTheDocument();
  });

  it("ouvre la liste entière au clic, et l'annonce suit", async () => {
    searchParams = new URLSearchParams();
    const user = userEvent.setup();
    render(<PodiumsList participations={NEUF} />);

    await user.click(screen.getByRole("button", { name: "Voir les 3 autres podiums" }));

    expect(screen.getAllByRole("listitem")).toHaveLength(9);
    expect(screen.queryByRole("button", { name: /Voir les/ })).not.toBeInTheDocument();
    // L'`AnnonceStatut` en place reflète le décompte affiché : l'extension est
    // annoncée sans région live supplémentaire (WCAG 4.1.3, cf. #477).
    expect(screen.getByText("9 podiums affichés")).toBeInTheDocument();
  });

  it("accorde le singulier quand il ne reste qu'un podium", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList participations={NEUF.slice(0, APERCU_PODIUMS + 1)} />);

    expect(screen.getByRole("button", { name: "Voir l'autre podium" })).toBeInTheDocument();
  });

  // Revue finale (#488) : le bouton se démontait à l'extension, faisant
  // perdre le focus clavier au `<body>`. Il devient une bascule.
  it("réduit la liste au second clic, focus préservé, et l'annonce suit", async () => {
    searchParams = new URLSearchParams();
    const user = userEvent.setup();
    render(<PodiumsList participations={NEUF} />);

    const bouton = screen.getByRole("button", { name: "Voir les 3 autres podiums" });
    await user.click(bouton);

    const reduire = screen.getByRole("button", { name: "Réduire la liste" });
    expect(reduire).toBe(bouton); // même élément DOM : jamais démonté
    await user.click(reduire);

    expect(screen.getAllByRole("listitem")).toHaveLength(APERCU_PODIUMS);
    expect(screen.getByRole("button", { name: "Voir les 3 autres podiums" })).toHaveFocus();
    expect(screen.getByText("6 podiums affichés")).toBeInTheDocument();
  });
});
