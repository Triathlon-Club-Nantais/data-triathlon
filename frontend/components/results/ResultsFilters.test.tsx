import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildResultsQuery, ResultsFilters } from "./ResultsFilters";
import { nomComplet, writeAthlete } from "@/components/layout/AthletePicker";

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

  it("« Filtrer » du volet pousse l'URL et ferme le volet (#485 — même verbe qu'en bandeau)", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    const dialogue = await screen.findByRole("dialog");
    const [, epreuveVolet] = screen.getAllByLabelText("Épreuve");
    fireEvent.change(epreuveVolet, { target: { value: "nantes" } });
    await userEvent.click(within(dialogue).getByRole("button", { name: "Filtrer" }));

    expect(push).toHaveBeenCalledWith(expect.stringContaining("event_name=nantes"));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("se ferme par la croix du volet sans modifier l'URL (#485)", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    const dialogue = await screen.findByRole("dialog");
    await userEvent.click(within(dialogue).getByRole("button", { name: "Fermer les filtres" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(push).not.toHaveBeenCalled();
  });

  it("fermer le volet sans appliquer (Échap) ne laisse pas une discipline abandonnée s'appliquer via Entrée dans « Athlète » (#I2)", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");
    const [, disciplineVolet] = screen.getAllByLabelText("Discipline");
    await userEvent.click(disciplineVolet);
    await userEvent.click(await screen.findByRole("option", { name: /triathlon m/i }));

    await userEvent.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    await userEvent.type(screen.getByPlaceholderText("Rechercher un athlète"), "mar{Enter}");

    expect(push).toHaveBeenCalledWith(expect.stringContaining("name=mar"));
    expect(push.mock.calls.at(-1)?.[0]).not.toContain("event_type=");
  });

  it("rouvrir le volet après un abandon (Échap) ne montre plus la discipline abandonnée comme active (#I2)", async () => {
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");
    const [, disciplineVolet] = screen.getAllByLabelText("Discipline");
    await userEvent.click(disciplineVolet);
    await userEvent.click(await screen.findByRole("option", { name: /triathlon m/i }));

    await userEvent.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");
    const [, disciplineReouverte] = screen.getAllByLabelText("Discipline");
    expect(disciplineReouverte).toHaveTextContent("Toutes les disciplines");
  });

  it("le « Réinitialiser » du bandeau se replie sous `sm`, comme « Filtrer » (#M1)", () => {
    searchParams = new URLSearchParams("name=marie");
    render(<ResultsFilters />);

    expect(screen.getByRole("button", { name: "Réinitialiser" }).className).toMatch(
      /(^|\s)hidden(\s|$)/,
    );
  });

  it("« Réinitialiser ces filtres » du volet ne remet pas à zéro le champ « Athlète », qui n'y figure pas (#M2, #485)", async () => {
    searchParams = new URLSearchParams("name=marie");
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Filtres" }));
    await screen.findByRole("dialog");
    await userEvent.click(screen.getByRole("button", { name: "Réinitialiser ces filtres" }));

    expect(push).toHaveBeenCalledWith(expect.stringContaining("name=marie"));
  });

  it("annonce l'état du volet sur le bouton « Filtres » (aria-expanded, aria-haspopup, #485)", async () => {
    render(<ResultsFilters />);

    const bouton = screen.getByRole("button", { name: "Filtres" });
    expect(bouton).toHaveAttribute("aria-haspopup", "dialog");
    expect(bouton).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(bouton);
    await screen.findByRole("dialog");

    expect(bouton).toHaveAttribute("aria-expanded", "true");
  });
});

const JEAN = { id: 12, prenom: "Jean", nom: "Dupont" };

describe("ResultsFilters — pastille de l'athlète retenu (NAV-10, #503)", () => {
  // Restauré en `afterEach` : sans lui, le prochain `describe` hériterait en
  // silence de ce faux `localStorage`.
  const descripteurOriginal = Object.getOwnPropertyDescriptor(window, "localStorage")!;

  beforeEach(() => {
    push.mockReset();
    replace.mockReset();
    searchParams = new URLSearchParams();
    const stock = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (cle: string) => stock.get(cle) ?? null,
        setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
        removeItem: (cle: string) => void stock.delete(cle),
        clear: () => stock.clear(),
      },
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "localStorage", descripteurOriginal);
  });

  it("ne propose rien quand aucun athlète n'est retenu", () => {
    render(<ResultsFilters />);
    expect(screen.queryByRole("button", { name: /Mes résultats/ })).not.toBeInTheDocument();
  });

  it("propose le filtre sans jamais l'appliquer au chargement", () => {
    writeAthlete(JEAN);
    render(<ResultsFilters />);

    expect(screen.getByRole("button", { name: "Mes résultats — Jean Dupont" })).toBeInTheDocument();
    // Le cœur de NAV-10 : proposé, jamais posé en silence.
    expect(push).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it("pose ?name=<nom complet> au clic, les autres filtres conservés", async () => {
    writeAthlete(JEAN);
    searchParams = new URLSearchParams("event_type=triathlon-m&scope=club");
    render(<ResultsFilters />);

    await userEvent.click(screen.getByRole("button", { name: "Mes résultats — Jean Dupont" }));

    expect(push).toHaveBeenCalledWith(expect.stringContaining("name=Jean+Dupont"));
    expect(push).toHaveBeenCalledWith(expect.stringContaining("event_type=triathlon-m"));
    expect(push).toHaveBeenCalledWith(expect.stringContaining("scope=club"));
  });

  it("disparaît une fois le filtre posé — le chip actif porte déjà la révocation", () => {
    writeAthlete(JEAN);
    searchParams = new URLSearchParams(`name=${nomComplet(JEAN)}`);
    render(<ResultsFilters />);

    expect(screen.queryByRole("button", { name: /Mes résultats/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retirer Athlète : Jean Dupont" })).toBeInTheDocument();
  });

  it("disparaît aussi quand le filtre posé diffère seulement par la casse ou les accents", () => {
    // « jean dupont » tapé à la main et « Jean Dupont » retenu désignent le
    // même filtre : sans comparaison insensible, la pastille et le chip actif
    // s'affichaient en même temps pour dire la même chose (revue #503).
    writeAthlete(JEAN);
    searchParams = new URLSearchParams("name=jean dupont");
    render(<ResultsFilters />);

    expect(screen.queryByRole("button", { name: /Mes résultats/ })).not.toBeInTheDocument();
  });
});
