import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/admin/AthleteClaimsTable", () => ({ AthleteClaimsTable: () => <p>file des fiches</p> }));
vi.mock("@/components/admin/ResultClaimsTable", () => ({ ResultClaimsTable: () => <p>file des résultats</p> }));
vi.mock("@/components/admin/AthleteLinksTable", () => ({ AthleteLinksTable: () => <p>comptes</p> }));

import AdminRattachementsPage from "./page";

describe("/admin/rattachements (#1637)", () => {
  it("keeps the two kinds of requests in distinct, labelled sections", () => {
    render(<AdminRattachementsPage />);

    const fiches = screen.getByRole("region", { name: /Fiches demandées/ });
    expect(within(fiches).getByText("Fiche entière")).toBeInTheDocument();
    expect(within(fiches).getByText(/Rattacher la fiche/)).toBeInTheDocument();
    expect(within(fiches).getByText("file des fiches")).toBeInTheDocument();

    const resultats = screen.getByRole("region", { name: /Résultats réclamés/ });
    expect(within(resultats).getByText("Un résultat")).toBeInTheDocument();
    expect(within(resultats).getByText(/Déplacer le résultat/)).toBeInTheDocument();
    expect(within(resultats).getByText("file des résultats")).toBeInTheDocument();

    expect(screen.getByRole("region", { name: "Comptes rattachés" })).toBeInTheDocument();
  });
});
