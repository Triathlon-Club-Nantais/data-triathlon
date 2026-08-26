import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { RosterApercu } from "./RosterApercu";
import { writeAthlete } from "@/components/layout/AthletePicker";
import type { RosterEntry } from "@/lib/utils/club-aggregate";

function entry(over: Partial<RosterEntry> & { athleteId: number }): RosterEntry {
  return {
    name: `Athlète ${over.athleteId}`,
    gender: "F",
    club: "TCN",
    count: 1,
    podiums: 0,
    podiumsByScope: { overall: 0, gender: 0, category: 0 },
    lastDate: null,
    lastEvent: null,
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
    const roster = [entry({ athleteId: 1, count: 3 }), entry({ athleteId: 2, count: 2 })];
    render(<RosterApercu roster={roster} apercuTaille={12} />);

    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
    expect(screen.queryByText(/du club/)).not.toBeInTheDocument();
  });

  it("marque ma fiche d'un chip, sans rappel, quand elle est dans l'aperçu", () => {
    writeAthlete({ id: 2, prenom: "P", nom: "Athlète 2" });
    const roster = [entry({ athleteId: 1, count: 3 }), entry({ athleteId: 2, count: 2 })];
    render(<RosterApercu roster={roster} apercuTaille={12} />);

    const marque = screen.getByText("Vous");
    expect(marque.closest("a")).toHaveTextContent("Athlète 2");
    expect(screen.queryByText(/du club/)).not.toBeInTheDocument();
  });

  it("affiche un rappel épinglé, lien vers /club/athletes ancré, quand je suis hors de l'aperçu", () => {
    const roster = Array.from({ length: 12 }, (_, i) =>
      entry({ athleteId: i + 1, count: 12 - i + 1 }),
    );
    roster.push(entry({ athleteId: 99, count: 1 }));
    writeAthlete({ id: 99, prenom: "M", nom: "Moi" });

    render(<RosterApercu roster={roster} apercuTaille={12} />);

    expect(screen.queryByText("Vous")).not.toBeInTheDocument();
    const rappel = screen.getByRole("link", { name: /Vous : 1 épreuve — 13ᵉ du club/ });
    expect(rappel).toHaveAttribute("href", "/club/athletes#athlete-99");
  });
});
