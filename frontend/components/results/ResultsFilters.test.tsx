import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildResultsQuery, ResultsFilters } from "./ResultsFilters";

describe("buildResultsQuery", () => {
  it("ignore les champs vides", () => {
    expect(buildResultsQuery({ name: "marie", event_type: "" })).toBe("name=marie");
  });
  it("encode plusieurs filtres", () => {
    const qs = buildResultsQuery({ name: "x", event_type: "triathlon-m", club: "nantais" });
    expect(qs).toContain("name=x");
    expect(qs).toContain("event_type=triathlon-m");
    expect(qs).toContain("club=nantais");
  });
  it("renvoie une chaîne vide si tout est vide", () => {
    expect(buildResultsQuery({})).toBe("");
  });
});

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => new URLSearchParams(),
}));

describe("ResultsFilters — recherche live", () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
  });

  it("filtre sur le nom d'athlète dès la frappe, sans clic ni Entrée", async () => {
    render(<ResultsFilters />);

    await userEvent.type(screen.getByPlaceholderText("Rechercher un athlète"), "mar");

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith(expect.stringContaining("name=mar"));
    });
  });

  it("filtre sur le nom de course dès la frappe, sans clic ni Entrée", async () => {
    render(<ResultsFilters />);

    await userEvent.type(screen.getByPlaceholderText("Rechercher une course"), "nantes");

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith(expect.stringContaining("event_name=nantes"));
    });
  });

  it("n'empile pas d'entrée d'historique par groupe de frappe (utilise replace, pas push)", async () => {
    render(<ResultsFilters />);

    await userEvent.type(screen.getByPlaceholderText("Rechercher un athlète"), "mar");

    await waitFor(() => {
      expect(replace).toHaveBeenCalled();
    });
    expect(push).not.toHaveBeenCalled();
  });

  it("le bouton Filtrer applique toujours via push (entrée d'historique explicite)", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtrer" }));

    expect(push).toHaveBeenCalled();
  });
});
