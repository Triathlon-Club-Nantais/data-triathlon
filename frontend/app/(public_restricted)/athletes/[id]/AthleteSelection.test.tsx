import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readAthlete } from "@/components/layout/AthletePicker";
import { AthleteSelection } from "./AthleteSelection";

const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont" };
const AUTRE = { id: 99, prenom: "Marie", nom: "Gaudin" };

const BENEFICE = "Choisir cet athlète pour retrouver ses résultats en un geste et se comparer au club";

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

describe("AthleteSelection", () => {
  it("propose de choisir quand l'athlète affiché n'est pas retenu", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Choisir cet athlète" })).toBeInTheDocument();
  });

  it("sélectionne au clic et bascule sur « Ne plus choisir cet athlète »", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: "Choisir cet athlète" }));

    expect(readAthlete()).toEqual(ATHLETE);
    expect(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" })).toBeInTheDocument();
  });

  it("propose « Ne plus choisir cet athlète » quand l'athlète affiché est déjà retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" })).toBeInTheDocument();
  });

  it("relâche au clic et repasse sur « Choisir cet athlète »", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" }));

    expect(readAthlete()).toBeNull();
    expect(await screen.findByRole("button", { name: "Choisir cet athlète" })).toBeInTheDocument();
  });

  it("propose « Choisir » quand un autre athlète est retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(AUTRE));
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Choisir cet athlète" })).toBeInTheDocument();
  });

  // #467 — l'état « c'est vous » se lit sans passer par le libellé du bouton.
  it("affiche la pastille « C'est vous » quand l'athlète affiché est retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByText("C'est vous")).toBeInTheDocument();
  });

  it("n'affiche pas la pastille quand l'athlète affiché n'est pas retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(AUTRE));
    render(<AthleteSelection athlete={ATHLETE} />);
    await screen.findByRole("button", { name: "Choisir cet athlète" });
    expect(screen.queryByText("C'est vous")).not.toBeInTheDocument();
  });

  it("fait apparaître la pastille au clic et disparaître au relâchement", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: "Choisir cet athlète" }));
    expect(await screen.findByText("C'est vous")).toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" }));
    expect(screen.queryByText("C'est vous")).not.toBeInTheDocument();
  });

  // #467 — le bénéfice répond à « pour quoi faire ? » au moment du clic.
  it("nomme le bénéfice sous le bouton non retenu, et le rattache au bouton", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    const bouton = await screen.findByRole("button", { name: "Choisir cet athlète" });
    const benefice = screen.getByText(BENEFICE);

    expect(benefice).toBeInTheDocument();
    expect(bouton).toHaveAttribute("aria-describedby", benefice.id);
  });

  it("retire le bénéfice quand l'athlète est déjà retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    await screen.findByRole("button", { name: "Ne plus choisir cet athlète" });
    expect(screen.queryByText(BENEFICE)).not.toBeInTheDocument();
  });

  // #467 — hiérarchie inversée : l'appel à l'action est primaire, sa révocation
  // secondaire. Le libellé n'est plus le seul porteur de l'état.
  it("rend le bouton primaire non retenu et secondaire retenu", async () => {
    const { unmount } = render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Choisir cet athlète" })).toHaveClass("tcn-btn--primary");
    unmount();

    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: "Ne plus choisir cet athlète" })).toHaveClass("tcn-btn--secondary");
  });
});
