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

describe("ResultsFilters — libellés associés (WCAG 3.3.2)", () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    searchParams = new URLSearchParams();
  });

  it("associe chacun des cinq libellés à son champ", () => {
    render(<ResultsFilters />);

    // Un `<label>` posé à côté d'un `<input>` n'est pas un libellé : un lecteur
    // d'écran annonçait « Du » et « Au » comme deux champs de date anonymes.
    expect(screen.getByLabelText("Athlète")).toBeInTheDocument();
    expect(screen.getByLabelText("Épreuve")).toBeInTheDocument();
    expect(screen.getByLabelText("Discipline")).toBeInTheDocument();
    expect(screen.getByLabelText("Du")).toBeInTheDocument();
    expect(screen.getByLabelText("Au")).toBeInTheDocument();
  });

  it("associe les deux dates par htmlFor/id, pas par proximité", () => {
    render(<ResultsFilters />);

    const du = screen.getByLabelText("Du");
    expect(du).toHaveAttribute("type", "date");
    expect(du.id).toBeTruthy();
  });
});

describe("ResultsFilters — volet mobile", () => {
  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    searchParams = new URLSearchParams();
  });

  it("porte le nombre de filtres repliés actifs, athlète non compté", () => {
    // « Athlète » reste visible hors du volet : il ne fait pas partie du compte.
    searchParams = new URLSearchParams("name=marie&event_type=triathlon-m&date_from=2026-01-01");
    render(<ResultsFilters />);

    expect(screen.getByRole("button", { name: "Filtres (2)" })).toBeInTheDocument();
  });

  it("n'affiche aucun compte quand aucun filtre replié n'est actif", () => {
    searchParams = new URLSearchParams("name=marie");
    render(<ResultsFilters />);

    expect(screen.getByRole("button", { name: "Filtres" })).toBeInTheDocument();
  });

  it("ouvre le volet et y rend les quatre champs repliés", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    // Deux rendus du même champ : l'inline (masqué sous `sm`) et celui du volet.
    expect(screen.getAllByLabelText("Épreuve")).toHaveLength(2);
    expect(screen.getAllByLabelText("Du")).toHaveLength(2);
  });

  it("ne duplique aucun identifiant entre le rendu inline et celui du volet", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");

    const ids = screen.getAllByLabelText("Épreuve").map((champ) => champ.id);
    expect(new Set(ids).size).toBe(2);
  });

  it("« Appliquer » pousse l'URL et ferme le volet", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");
    const [, epreuveVolet] = screen.getAllByLabelText("Épreuve");
    fireEvent.change(epreuveVolet, { target: { value: "nantes" } });
    await userEvent.click(screen.getByRole("button", { name: "Appliquer" }));

    expect(push).toHaveBeenCalledWith(expect.stringContaining("event_name=nantes"));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
