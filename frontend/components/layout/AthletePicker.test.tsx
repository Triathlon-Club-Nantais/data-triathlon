import { StrictMode } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  readAthlete,
  writeAthlete,
  clearAthlete,
  nomComplet,
  useSelectedAthlete,
  AthletePicker,
} from "./AthletePicker";

const searchAthletes = vi.fn();
vi.mock("@/lib/api/client", () => ({
  apiClient: { searchAthletes: (q: string, limit?: number) => searchAthletes(q, limit) },
}));

const ATHLETE = { id: 7, prenom: "Marie", nom: "Gaudin" };

beforeEach(() => {
  // Node 20 (la CI) fournit `window.localStorage` à jsdom, Node 26 non — même
  // stock déterministe que `AppNav.test.tsx`.
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

describe("microcopie — un seul nom pour l'objet (#502)", () => {
  it("nomme la modale « Mon athlète »", () => {
    render(<AthletePicker onClose={() => {}} onPick={() => {}} />);
    expect(screen.getByText("Mon athlète")).toBeInTheDocument();
    expect(screen.queryByText("Accès athlète")).not.toBeInTheDocument();
  });

  // Le pied rassurait sur une inquiétude que personne n'a exprimée ; il énonce
  // désormais ce que le choix rapporte (audit § 10, gradient de but).
  //
  // #502, revue UI/UX item 9 : la promesse a divergé de ce qui arrive
  // réellement — « vos résultats » ici, « voir sa saison » sous le bouton du
  // rail, et le bloc livré s'appelle « Ma saison » et montre deux compteurs,
  // pas des résultats. Les trois s'alignent désormais sur le nom du bloc.
  it("énonce la promesse au moment du choix", () => {
    render(<AthletePicker onClose={() => {}} onPick={() => {}} />);
    expect(
      screen.getByText("Votre saison s'affichera en tête du tableau de bord."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Pas de blocage d'accès/)).not.toBeInTheDocument();
    expect(
      screen.queryByText("Votre tableau de bord affichera vos résultats en premier."),
    ).not.toBeInTheDocument();
  });
});

describe("clearAthlete", () => {
  it("supprime la sélection retenue", () => {
    writeAthlete(ATHLETE);
    expect(readAthlete()).toEqual(ATHLETE);

    clearAthlete();
    expect(readAthlete()).toBeNull();
  });
});

describe("AthletePicker — aucune correspondance (ETAT-3)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    searchAthletes.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("propose d'effacer la recherche quand rien ne correspond", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Rechercher un nom…"), "zzz");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    // The status region (#996) repeats the title for screen readers.
    expect(
      await screen.findByText("Aucun athlète trouvé", { ignore: "script, style, [role=status]" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Effacer la recherche" }));
    expect(screen.getByPlaceholderText("Rechercher un nom…")).toHaveValue("");
  });
});

describe("AthletePicker — classement par pertinence, servi par l'API (NAV-8, #484)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("affiche les résultats dans l'ordre rendu par l'API, sans les retrier par volume", async () => {
    searchAthletes.mockResolvedValue([
      { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "", club: "TCN", participation_count: 3 },
      { id: 2, nom: "HERRY", prenom: "Yves", gender: "", club: "TCN", participation_count: 5 },
    ]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Rechercher un nom…"), "herr");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    const noms = (await screen.findAllByText(/Mathieu HERRMANN|Yves HERRY/)).map(
      (el) => el.textContent,
    );
    expect(noms).toEqual(["Mathieu HERRMANN", "Yves HERRY"]);
    expect(searchAthletes).toHaveBeenCalledWith("herr", 13);
  });

  it("affiche le nombre de participations rendu par l'API", async () => {
    searchAthletes.mockResolvedValue([
      { id: 1, nom: "GAUDIN", prenom: "Marie", gender: "", club: "TCN", participation_count: 3 },
    ]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Rechercher un nom…"), "gaudin");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(await screen.findByText(/3 épreuves/)).toBeInTheDocument();
  });
});

describe("AthletePicker — ARIA combobox and listbox (#996)", () => {
  const DEUX = [
    { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "", club: "TCN", participation_count: 3 },
    { id: 2, nom: "HERRY", prenom: "Yves", gender: "", club: "TCN", participation_count: 5 },
  ];

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function chercher(terme: string, onPick = vi.fn()) {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={onPick} />);
    await user.type(screen.getByRole("combobox"), terme);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    return user;
  }

  it("exposes the field as a combobox that controls the results listbox", async () => {
    searchAthletes.mockResolvedValue(DEUX);
    await chercher("herr");

    const champ = screen.getByRole("combobox");
    const liste = await screen.findByRole("listbox", { name: "Athlètes trouvés" });
    expect(champ).toHaveAttribute("aria-autocomplete", "list");
    expect(champ).toHaveAttribute("aria-expanded", "true");
    expect(champ).toHaveAttribute("aria-controls", liste.id);
    expect(screen.getAllByRole("option")).toHaveLength(2);
    expect(champ).not.toHaveAttribute("aria-activedescendant");
  });

  it("is collapsed while there is nothing to list", () => {
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);

    expect(screen.getByRole("combobox")).toHaveAttribute("aria-expanded", "false");
  });

  it("moves the active option with the arrow keys, bounded at both ends", async () => {
    searchAthletes.mockResolvedValue(DEUX);
    const user = await chercher("herr");
    await screen.findByRole("listbox");
    const champ = screen.getByRole("combobox");
    const [premier, second] = screen.getAllByRole("option");

    await user.keyboard("{ArrowDown}");
    expect(champ).toHaveFocus();
    expect(champ).toHaveAttribute("aria-activedescendant", premier.id);
    expect(premier).toHaveAttribute("aria-selected", "true");
    expect(second).toHaveAttribute("aria-selected", "false");

    await user.keyboard("{ArrowDown}{ArrowDown}");
    expect(champ).toHaveAttribute("aria-activedescendant", second.id);

    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(champ).toHaveAttribute("aria-activedescendant", premier.id);
  });

  it("picks the active option on Enter", async () => {
    searchAthletes.mockResolvedValue(DEUX);
    const onPick = vi.fn();
    const user = await chercher("herr", onPick);
    await screen.findByRole("listbox");

    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");

    expect(onPick).toHaveBeenCalledWith({ id: 2, prenom: "Yves", nom: "HERRY" });
  });

  it("announces each search state in a status region", async () => {
    searchAthletes.mockResolvedValue(DEUX);
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("Saisissez au moins 2 lettres");

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.type(screen.getByRole("combobox"), "herr");
    expect(screen.getByRole("status")).toHaveTextContent("Recherche…");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(screen.getByRole("status")).toHaveTextContent("2 athlètes trouvés");
  });

  it("announces a single result and an empty search", async () => {
    searchAthletes.mockResolvedValueOnce([DEUX[0]]).mockResolvedValueOnce([]);
    const user = await chercher("herrm");
    expect(screen.getByRole("status")).toHaveTextContent("1 athlète trouvé");

    await user.type(screen.getByRole("combobox"), "zz");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(screen.getByRole("status")).toHaveTextContent("Aucun athlète trouvé");
  });

  it("announces more than 12 results instead of the truncated count", async () => {
    searchAthletes.mockResolvedValue(
      Array.from({ length: 13 }, (_, i) => ({ ...DEUX[0], id: i + 1 })),
    );
    await chercher("herr");
    expect(screen.getAllByRole("option")).toHaveLength(12);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Plus de 12 athlètes trouvés, précisez la recherche",
    );
    expect(
      screen.getByText("Plus de 12 athlètes trouvés, précisez la recherche", {
        ignore: "[role=status], [role=status] *",
      }),
    ).toBeVisible();
  });

  it("outlines the active option so keyboard users can see it", async () => {
    searchAthletes.mockResolvedValue(DEUX);
    const user = await chercher("herr");
    await user.keyboard("{ArrowDown}");
    const [premier, second] = screen.getAllByRole("option");
    expect(premier.style.outline).toBe("2px solid var(--tcn-orange)");
    expect(second.style.outline).toBe("");
  });

  it("names each option with club and event count so homonyms differ (#998)", async () => {
    searchAthletes.mockResolvedValue([
      { id: 1, nom: "Dupont", prenom: "Jean", gender: "", club: "TCN", participation_count: 3 },
      { id: 2, nom: "Dupont", prenom: "Jean", gender: "", club: null, participation_count: 1 },
    ]);
    await chercher("dupont");

    expect(
      await screen.findByRole("option", { name: "Choisir Jean Dupont, TCN, 3 épreuves" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Choisir Jean Dupont, Sans club, 1 épreuve" }),
    ).toBeInTheDocument();
  });

  it("renders no listbox and no aria-controls without results", () => {
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).not.toHaveAttribute("aria-controls");
  });
});

describe("événement de synchronisation tcn-athlete-changed", () => {
  it("est émis par writeAthlete", () => {
    const ecouteur = vi.fn();
    window.addEventListener("tcn-athlete-changed", ecouteur);
    writeAthlete(ATHLETE);
    expect(ecouteur).toHaveBeenCalledTimes(1);
  });

  it("est émis par clearAthlete", () => {
    const ecouteur = vi.fn();
    window.addEventListener("tcn-athlete-changed", ecouteur);
    clearAthlete();
    expect(ecouteur).toHaveBeenCalledTimes(1);
  });
});

function SondeAthlete() {
  const athlete = useSelectedAthlete();
  return <div data-testid="sonde">{athlete ? nomComplet(athlete) : "aucun"}</div>;
}

describe("useSelectedAthlete", () => {
  it("rend null quand aucun athlète n'est retenu", () => {
    render(<SondeAthlete />);
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");
  });

  it("rend l'athlète retenu sans boucler — le snapshot est mémorisé", () => {
    // Sans cache, `getSnapshot` rendrait un objet neuf à chaque rendu et React
    // lèverait « The result of getSnapshot should be cached to avoid an
    // infinite loop » : ce rendu, en StrictMode (deux passes), est la seule
    // façon d'établir la stabilité de la référence depuis l'extérieur.
    writeAthlete(ATHLETE);
    render(
      <StrictMode>
        <SondeAthlete />
      </StrictMode>,
    );
    expect(screen.getByTestId("sonde")).toHaveTextContent("Marie Gaudin");
  });

  it("se resynchronise quand le stock change, sans remontage", () => {
    render(<SondeAthlete />);
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");

    act(() => writeAthlete(ATHLETE));
    expect(screen.getByTestId("sonde")).toHaveTextContent("Marie Gaudin");

    act(() => clearAthlete());
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");
  });
});
