import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { RosterApercu } from "./RosterApercu";
import { writeAthlete } from "@/components/layout/AthletePicker";
import type { ClubRosterEntry } from "@/lib/types";

function entry(over: Partial<ClubRosterEntry> & { athlete_id: number }): ClubRosterEntry {
  return {
    prenom: "P",
    nom: `Athlète ${over.athlete_id}`,
    count: 1,
    podiums: 0,
    podiums_overall: 0,
    podiums_gender: 0,
    podiums_category: 0,
    ...over,
  };
}

describe("RosterApercu — retrouver sa ligne (#504)", () => {
  const descripteurOriginal = Object.getOwnPropertyDescriptor(window, "localStorage")!;

  beforeEach(() => {
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

  it("ne marque aucune fiche et n'affiche pas de rappel quand aucun athlète n'est retenu", () => {
    const roster = [entry({ athlete_id: 1, count: 3 }), entry({ athlete_id: 2, count: 2 })];
    render(<RosterApercu roster={roster} />);

    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
    expect(screen.queryByText(/n'êtes pas parmi/)).not.toBeInTheDocument();
  });

  it("marque ma fiche d'un chip, sans rappel, quand elle est dans l'aperçu", () => {
    writeAthlete({ id: 2, prenom: "P", nom: "Athlète 2" });
    const roster = [entry({ athlete_id: 1, count: 3 }), entry({ athlete_id: 2, count: 2 })];
    render(<RosterApercu roster={roster} />);

    const marque = screen.getByText("Vous");
    expect(marque.closest("a")).toHaveTextContent("Athlète 2");
    expect(screen.queryByText(/n'êtes pas parmi/)).not.toBeInTheDocument();
  });

  it("affiche un rappel générique, lien vers /club/athletes ancré, quand je suis hors de l'aperçu", () => {
    const roster = Array.from({ length: 12 }, (_, i) => entry({ athlete_id: i + 1, count: 12 - i + 1 }));
    writeAthlete({ id: 99, prenom: "M", nom: "Moi" });

    render(<RosterApercu roster={roster} />);

    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
    const rappel = screen.getByRole("link", { name: /n'êtes pas parmi les 12 athlètes/ });
    expect(rappel).toHaveAttribute("href", "/club/athletes#athlete-99");
  });
});
