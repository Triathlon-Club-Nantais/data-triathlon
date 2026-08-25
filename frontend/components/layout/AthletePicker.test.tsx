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

    expect(await screen.findByText("Aucun athlète trouvé")).toBeInTheDocument();
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
