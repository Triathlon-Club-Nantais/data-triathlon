import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readAthlete } from "@/components/layout/AthletePicker";
import { SelectAthleteButton } from "./SelectAthleteButton";

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

describe("SelectAthleteButton", () => {
  it("propose de choisir quand l'athlète affiché n'est pas retenu", async () => {
    render(<SelectAthleteButton athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Choisir cet athlète" })).toBeInTheDocument();
  });

  it("sélectionne au clic et bascule sur « Ne plus choisir cet athlète »", async () => {
    render(<SelectAthleteButton athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: "Choisir cet athlète" }));

    expect(readAthlete()).toEqual(ATHLETE);
    expect(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" })).toBeInTheDocument();
  });

  it("propose « Ne plus choisir cet athlète » quand l'athlète affiché est déjà retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<SelectAthleteButton athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" })).toBeInTheDocument();
  });

  it("relâche au clic et repasse sur « Choisir cet athlète »", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<SelectAthleteButton athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" }));

    expect(readAthlete()).toBeNull();
    expect(await screen.findByRole("button", { name: "Choisir cet athlète" })).toBeInTheDocument();
  });

  it("propose « Choisir » quand un autre athlète est retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(AUTRE));
    render(<SelectAthleteButton athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Choisir cet athlète" })).toBeInTheDocument();
  });
});
