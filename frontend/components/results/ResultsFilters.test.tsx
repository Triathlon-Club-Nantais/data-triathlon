import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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
let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
  useSearchParams: () => searchParams,
}));

describe("ResultsFilters — recherche live", () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    searchParams = new URLSearchParams();
  });

  it("filtre sur le nom d'athlète dès la frappe, sans clic ni Entrée", async () => {
    render(<ResultsFilters />);

    await userEvent.type(screen.getByPlaceholderText("Rechercher un athlète"), "mar");

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith(expect.stringContaining("name=mar"));
    });
  });

  it("filtre sur le nom d'épreuve dès la frappe, sans clic ni Entrée", async () => {
    render(<ResultsFilters />);

    await userEvent.type(screen.getByPlaceholderText("Rechercher une épreuve"), "nantes");

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

  it("ne propage pas un filtre discipline/dates modifié mais pas encore appliqué (#387)", async () => {
    // Changer la date sans cliquer sur "Filtrer" ne doit pas être appliqué
    // par la recherche live déclenchée par le champ texte : seuls les
    // champs texte filtrent dès la frappe, le reste attend une action
    // explicite (bouton, Entrée).
    const { container } = render(<ResultsFilters />);
    const dateFrom = container.querySelector('input[type="date"]');
    fireEvent.change(dateFrom as HTMLInputElement, { target: { value: "2026-01-01" } });

    await userEvent.type(screen.getByPlaceholderText("Rechercher un athlète"), "mar");

    await waitFor(() => {
      expect(replace).toHaveBeenCalled();
    });
    expect(replace.mock.calls.at(-1)?.[0]).not.toContain("date_from=");
  });

  it("porte la croix de retrait d'un chip de filtre à la taille tactile minimale (24 px, #479)", async () => {
    // WCAG 2.2 2.5.8 : 24 px CSS minimum. `size-3` + `p-0.5` (16 px) était
    // sous le plancher.
    searchParams = new URLSearchParams("name=marie");
    render(<ResultsFilters />);

    const croix = await screen.findByRole("button", { name: /retirer athlète/i });

    expect(croix.className).toMatch(/(^|\s)size-6(\s|$)/);
    expect(croix.parentElement?.className).toMatch(/(^|\s)h-7(\s|$)/);
  });
});
