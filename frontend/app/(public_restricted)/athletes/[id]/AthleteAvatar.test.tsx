import { describe, it, expect, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { writeAthlete } from "@/components/layout/AthletePicker";
import { AthleteAvatar } from "./AthleteAvatar";

const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont" };
const AUTRE = { id: 99, prenom: "Marie", nom: "Gaudin" };

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

describe("AthleteAvatar", () => {
  it("cercle l'avatar quand le profil affiché est l'athlète retenu", () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteAvatar athleteId={ATHLETE.id} name="Jean Dupont" />);
    expect(screen.getByTestId("athlete-avatar")).toHaveAttribute("data-selected", "true");
  });

  it("laisse l'avatar nu quand aucun athlète n'est retenu", () => {
    render(<AthleteAvatar athleteId={ATHLETE.id} name="Jean Dupont" />);
    expect(screen.getByTestId("athlete-avatar")).toHaveAttribute("data-selected", "false");
  });

  it("laisse l'avatar nu quand un autre athlète est retenu", () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(AUTRE));
    render(<AthleteAvatar athleteId={ATHLETE.id} name="Jean Dupont" />);
    expect(screen.getByTestId("athlete-avatar")).toHaveAttribute("data-selected", "false");
  });

  // Le choix se fait ailleurs dans la page (bouton de sélection) : l'anneau
  // suit sans rechargement, par le même événement que le rail de navigation.
  it("suit une sélection faite ailleurs dans la page", () => {
    render(<AthleteAvatar athleteId={ATHLETE.id} name="Jean Dupont" />);
    expect(screen.getByTestId("athlete-avatar")).toHaveAttribute("data-selected", "false");

    act(() => writeAthlete(ATHLETE));
    expect(screen.getByTestId("athlete-avatar")).toHaveAttribute("data-selected", "true");
  });

  it("garde les initiales de l'athlète", () => {
    render(<AthleteAvatar athleteId={ATHLETE.id} name="Jean Dupont" />);
    expect(screen.getByTestId("athlete-avatar")).toHaveTextContent("JD");
  });
});
