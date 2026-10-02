import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { ChallengeDetail } from "@/lib/types";
import { ApiError } from "@/lib/api/client";

const getChallenge = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: { getChallenge: (id: number) => getChallenge(id) },
}));

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("notFound");
  },
}));

import ChallengePage from "./page";

const CHALLENGE: ChallengeDetail = {
  id: 7,
  name: "MEDOC 2026 - START CHALLENGE (XS - M - L)",
  event_date: "2026-05-13",
  courses: [{ id: 284, name: "MEDOC 2026 - XS" }],
  results: [
    { athlete_id: 1, nom: "DUPONT", prenom: "Jean", rank_overall: 1, total_time: "06:50:33", status: "finisher" },
    { athlete_id: 2, nom: "MARTIN", prenom: "Paul", rank_overall: null, total_time: null, status: "DNF" },
  ],
};

async function afficher(id = "7") {
  render(await ChallengePage({ params: Promise.resolve({ id }) }));
}

describe("ChallengePage", () => {
  beforeEach(() => { getChallenge.mockReset(); });

  it("rend le titre, les épreuves liées et une ligne par résultat dans l'ordre reçu", async () => {
    getChallenge.mockResolvedValue(CHALLENGE);
    await afficher();

    expect(screen.getByRole("heading", { level: 1, name: CHALLENGE.name })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "MEDOC 2026 - XS" })).toHaveAttribute("href", "/courses/284");
    const lignes = within(screen.getByRole("table", { name: "Classement du challenge" })).getAllByRole("row");
    expect(lignes).toHaveLength(3);
    expect(within(lignes[1]).getByRole("link", { name: "Jean DUPONT" })).toHaveAttribute("href", "/athletes/1");
    expect(within(lignes[1]).getByText("06:50:33")).toBeInTheDocument();
    expect(within(lignes[2]).getByText("Abandon")).toBeInTheDocument();
  });

  it("appelle notFound sur un challenge inconnu", async () => {
    getChallenge.mockRejectedValue(new ApiError(404, "Challenge introuvable"));
    await expect(afficher("999")).rejects.toThrow("notFound");
  });
});
