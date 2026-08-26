import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ATHLETE_CHANGED_EVENT, ATHLETE_LOST_EVENT } from "@/components/layout/AthletePicker";
import { InvitationAthlete } from "./InvitationAthlete";

const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont" };

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

describe("InvitationAthlete — aucun athlète retenu", () => {
  it("invite à choisir un athlète", () => {
    render(<InvitationAthlete />);
    expect(
      screen.getByRole("button", { name: /retrouvez vos épreuves et vos podiums/i }),
    ).toBeInTheDocument();
  });

  it("le clic ouvre la palette (OPEN_PICKER_EVENT)", async () => {
    render(<InvitationAthlete />);
    const bouton = screen.getByRole("button", { name: /retrouvez vos épreuves et vos podiums/i });
    const ecouteur = vi.fn();
    window.addEventListener("tcn-athlete-open-picker", ecouteur);

    await act(async () => {
      bouton.click();
    });

    expect(ecouteur).toHaveBeenCalledTimes(1);
  });
});

describe("InvitationAthlete — un athlète est retenu", () => {
  it("ne rend rien", () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    const { container } = render(<InvitationAthlete />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("InvitationAthlete — fiche disparue (état « perdu » de MaSaison)", () => {
  it("se tait le temps que MaSaison affiche « Votre fiche a changé » (ATHLETE_LOST_EVENT)", async () => {
    render(<InvitationAthlete />);
    await screen.findByRole("button", { name: /retrouvez vos épreuves et vos podiums/i });

    await act(async () => {
      window.dispatchEvent(new Event(ATHLETE_LOST_EVENT));
    });

    expect(
      screen.queryByRole("button", { name: /retrouvez vos épreuves et vos podiums/i }),
    ).not.toBeInTheDocument();
  });

  it("réapparaît dès qu'un nouveau choix intervient (ATHLETE_CHANGED_EVENT)", async () => {
    render(<InvitationAthlete />);
    await act(async () => {
      window.dispatchEvent(new Event(ATHLETE_LOST_EVENT));
    });
    expect(
      screen.queryByRole("button", { name: /retrouvez vos épreuves et vos podiums/i }),
    ).not.toBeInTheDocument();

    await act(async () => {
      window.dispatchEvent(new Event(ATHLETE_CHANGED_EVENT));
    });

    expect(
      screen.getByRole("button", { name: /retrouvez vos épreuves et vos podiums/i }),
    ).toBeInTheDocument();
  });
});
