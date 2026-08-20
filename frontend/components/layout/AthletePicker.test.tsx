import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readAthlete, writeAthlete, clearAthlete, AthletePicker } from "./AthletePicker";

const listParticipations = vi.fn();
vi.mock("@/lib/api/client", () => ({
  apiClient: { listParticipations: (filters: unknown) => listParticipations(filters) },
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
    listParticipations.mockResolvedValue([]);
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
