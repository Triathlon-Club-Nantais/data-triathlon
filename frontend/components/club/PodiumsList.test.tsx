import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ClubPodiumEntry, ClubPodiums } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { PodiumsList, APERCU_PODIUMS } from "./PodiumsList";

function entry(over: Partial<ClubPodiumEntry> & { participation_id: number }): ClubPodiumEntry {
  return {
    participation_id: over.participation_id,
    athlete_id: over.athlete_id ?? over.participation_id,
    athlete_name: over.athlete_name ?? "P N",
    event_name: over.event_name ?? `Course ${over.participation_id}`,
    event_type: over.event_type ?? "triathlon-m",
    is_relay: over.is_relay ?? false,
    event_date: over.event_date ?? "2026-05-10",
    rank: over.rank ?? 1,
    scope: over.scope ?? "overall",
    total_time: over.total_time ?? "01:59:00",
  };
}

const EMPTY: ClubPodiums = { scratch: [], category: [], gender: [], all: [] };

const PODIUMS: ClubPodiums = {
  scratch: [entry({ participation_id: 2, scope: "overall", rank: 2 })],
  category: [entry({ participation_id: 1, scope: "category", rank: 1 })],
  gender: [entry({ participation_id: 3, scope: "gender", rank: 1 })],
  all: [
    entry({ participation_id: 1, scope: "category", rank: 1 }),
    entry({ participation_id: 2, scope: "overall", rank: 2 }),
    entry({ participation_id: 3, scope: "gender", rank: 1 }),
  ],
};

describe("PodiumsList — filtrage selon ?rank= (#104, #132, #581)", () => {
  it("sans ?rank= (défaut scratch) : n'affiche que les badges « Général »", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByText("Général")).toBeInTheDocument();
    expect(screen.queryByText("Catégorie")).not.toBeInTheDocument();
    expect(screen.queryByText("Genre")).not.toBeInTheDocument();
  });

  it("?rank=category : n'affiche que les badges « Catégorie »", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByText("Catégorie")).toBeInTheDocument();
    expect(screen.queryByText("Général")).not.toBeInTheDocument();
  });

  it("?rank=all : montre le mélange des trois scopes", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByText("Général")).toBeInTheDocument();
    expect(screen.getByText("Catégorie")).toBeInTheDocument();
    expect(screen.getByText("Genre")).toBeInTheDocument();
  });

  it("liste vide → message d'attente, aucun badge", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList podiums={EMPTY} />);
    expect(screen.getByText("Pas encore de podium enregistré.")).toBeInTheDocument();
  });
});

describe("PodiumsList — icône par scope (#128)", () => {
  it("?rank=all : chaque scope porte une icône avec aria-label distinct", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByLabelText("Podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("Podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("Podium de genre")).toBeInTheDocument();
  });
});

describe("PodiumsList — annonce du changement (#477)", () => {
  it("annonce le nombre de podiums affichés dans une région role=status", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByRole("status")).toHaveTextContent("1 podium affiché");
  });

  it("reste montée et annonce zéro quand la bascule ne laisse plus aucun podium (revue de code)", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList podiums={EMPTY} />);
    expect(screen.getByRole("status")).toHaveTextContent("0 podium affiché");
  });
});

describe("PodiumsList — extension de la liste (PROF-3, #488)", () => {
  const NEUF: ClubPodiums = {
    ...EMPTY,
    scratch: Array.from({ length: 9 }, (_, i) =>
      entry({ participation_id: i + 1, scope: "overall", rank: 1 }),
    ),
  };

  it("n'offre pas d'extension quand tout tient dans l'aperçu", () => {
    searchParams = new URLSearchParams();
    render(
      <PodiumsList
        podiums={{ ...EMPTY, scratch: NEUF.scratch.slice(0, APERCU_PODIUMS) }}
      />,
    );
    expect(screen.queryByRole("button", { name: /Voir les/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(APERCU_PODIUMS);
  });

  it("ouvre la liste entière au clic", async () => {
    searchParams = new URLSearchParams();
    const user = userEvent.setup();
    render(<PodiumsList podiums={NEUF} />);

    await user.click(screen.getByRole("button", { name: "Voir les 3 autres podiums" }));

    expect(screen.getAllByRole("listitem")).toHaveLength(9);
  });

  it("porte aria-expanded, à jour après le clic", async () => {
    searchParams = new URLSearchParams();
    const user = userEvent.setup();
    render(<PodiumsList podiums={NEUF} />);
    const bouton = screen.getByRole("button", { name: "Voir les 3 autres podiums" });
    expect(bouton).toHaveAttribute("aria-expanded", "false");
    await user.click(bouton);
    expect(screen.getByRole("button", { name: "Réduire la liste" })).toHaveAttribute("aria-expanded", "true");
  });

  it("réduit la liste au second clic, focus préservé, et l'annonce suit", async () => {
    searchParams = new URLSearchParams();
    const user = userEvent.setup();
    render(<PodiumsList podiums={NEUF} />);
    const bouton = screen.getByRole("button", { name: "Voir les 3 autres podiums" });
    await user.click(bouton);
    const reduire = screen.getByRole("button", { name: "Réduire la liste" });
    expect(reduire).toBe(bouton);
    await user.click(reduire);
    expect(screen.getAllByRole("listitem")).toHaveLength(APERCU_PODIUMS);
    expect(screen.getByRole("button", { name: "Voir les 3 autres podiums" })).toHaveFocus();
    expect(screen.getByText("6 podiums affichés")).toBeInTheDocument();
  });

  it("accorde le singulier quand il ne reste qu'un podium", () => {
    searchParams = new URLSearchParams();
    render(
      <PodiumsList
        podiums={{ ...EMPTY, scratch: NEUF.scratch.slice(0, APERCU_PODIUMS + 1) }}
      />,
    );
    expect(screen.getByRole("button", { name: "Voir l'autre podium" })).toBeInTheDocument();
  });
});
