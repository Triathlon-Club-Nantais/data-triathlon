import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readAthlete } from "@/components/layout/AthletePicker";
import { AthleteSelection } from "./AthleteSelection";

const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont" };
const AUTRE = { id: 99, prenom: "Marie", nom: "Gaudin" };

const BENEFICE =
  "Choisir cet athlète pour retrouver ses résultats en un geste et voir sa saison en tête du tableau de bord";

const TEXTE_CHOISIR = "Choisir cet athlète";
const TEXTE_RELACHER = "Ne plus choisir cet athlète";

const LABEL_CHOISIR = "Choisir cet athlète, Jean Dupont";
const LABEL_RELACHER = "Ne plus choisir cet athlète, Jean Dupont";
const LABEL_CHOISIR_AUTRE = "Choisir cet athlète, Marie Gaudin";
const LABEL_RELACHER_AUTRE = "Ne plus choisir cet athlète, Marie Gaudin";

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
    expect(await screen.findByRole("button", { name: LABEL_CHOISIR })).toBeInTheDocument();
  });

  it("sélectionne au clic et bascule sur « Ne plus choisir cet athlète »", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: LABEL_CHOISIR }));

    expect(readAthlete()).toEqual(ATHLETE);
    expect(await screen.findByRole("button", { name: LABEL_RELACHER })).toBeInTheDocument();
  });

  it("propose « Ne plus choisir cet athlète » quand l'athlète affiché est déjà retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: LABEL_RELACHER })).toBeInTheDocument();
  });

  it("relâche au clic et repasse sur « Choisir cet athlète »", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: LABEL_RELACHER }));

    expect(readAthlete()).toBeNull();
    expect(await screen.findByRole("button", { name: LABEL_CHOISIR })).toBeInTheDocument();
  });

  it("propose « Choisir » quand un autre athlète est retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(AUTRE));
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: LABEL_CHOISIR })).toBeInTheDocument();
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
    await screen.findByRole("button", { name: LABEL_CHOISIR });
    expect(screen.queryByText("C'est vous")).not.toBeInTheDocument();
  });

  it("fait apparaître la pastille au clic et disparaître au relâchement", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    await userEvent.click(await screen.findByRole("button", { name: LABEL_CHOISIR }));
    expect(await screen.findByText("C'est vous")).toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: LABEL_RELACHER }));
    expect(screen.queryByText("C'est vous")).not.toBeInTheDocument();
  });

  // #467 — le bénéfice répond à « pour quoi faire ? » au moment du clic.
  it("nomme le bénéfice sous le bouton non retenu, et le rattache au bouton", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    const bouton = await screen.findByRole("button", { name: LABEL_CHOISIR });
    const benefice = screen.getByText(BENEFICE);

    expect(benefice).toBeInTheDocument();
    expect(bouton).toHaveAttribute("aria-describedby", benefice.id);
  });

  it("retire le bénéfice quand l'athlète est déjà retenu", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    await screen.findByRole("button", { name: LABEL_RELACHER });
    expect(screen.queryByText(BENEFICE)).not.toBeInTheDocument();
  });

  // #467 — hiérarchie inversée : l'appel à l'action est primaire, sa révocation
  // secondaire. Le libellé n'est plus le seul porteur de l'état.
  it("rend le bouton primaire non retenu et secondaire retenu", async () => {
    const { unmount } = render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: LABEL_CHOISIR })).toHaveClass("tcn-btn--primary");
    unmount();

    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(await screen.findByRole("button", { name: LABEL_RELACHER })).toHaveClass("tcn-btn--secondary");
  });

  it("nomme le bénéfice réellement rendu par le tableau de bord (#502)", () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    expect(
      screen.getByText(
        "Choisir cet athlète pour retrouver ses résultats en un geste et voir sa saison en tête du tableau de bord",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/se comparer au club/)).not.toBeInTheDocument();
  });

  // #752 — audit UI/UX : le nom accessible des deux boutons était leur texte
  // visible générique. Vérifie que l'aria-label porte bien le nom de
  // l'athlète affiché, et qu'il varie avec lui (pas un texte figé).
  it("porte le nom de l'athlète dans l'aria-label du bouton de choix (WCAG 4.1.2)", async () => {
    render(<AthleteSelection athlete={AUTRE} />);
    const bouton = await screen.findByRole("button", { name: LABEL_CHOISIR_AUTRE });
    expect(bouton).toHaveAttribute("aria-label", LABEL_CHOISIR_AUTRE);
  });

  it("porte le nom de l'athlète dans l'aria-label du bouton de relâchement (WCAG 4.1.2)", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(AUTRE));
    render(<AthleteSelection athlete={AUTRE} />);
    const bouton = await screen.findByRole("button", { name: LABEL_RELACHER_AUTRE });
    expect(bouton).toHaveAttribute("aria-label", LABEL_RELACHER_AUTRE);
  });

  // #752 (revue UI/UX finale) — WCAG 2.5.3 « Label in Name » : le nom
  // accessible doit *contenir* le texte visible, pas le remplacer, sinon un
  // utilisateur de commande vocale qui dit le texte qu'il voit à l'écran ne
  // peut plus activer le bouton.
  it("garde le texte visible du bouton de choix comme préfixe littéral de son aria-label (WCAG 2.5.3)", async () => {
    render(<AthleteSelection athlete={ATHLETE} />);
    const bouton = await screen.findByRole("button", { name: LABEL_CHOISIR });
    expect(bouton).toHaveTextContent(TEXTE_CHOISIR);
    expect(bouton.getAttribute("aria-label")).toMatch(new RegExp(`^${TEXTE_CHOISIR}`));
  });

  it("garde le texte visible du bouton de relâchement comme préfixe littéral de son aria-label (WCAG 2.5.3)", async () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<AthleteSelection athlete={ATHLETE} />);
    const bouton = await screen.findByRole("button", { name: LABEL_RELACHER });
    expect(bouton).toHaveTextContent(TEXTE_RELACHER);
    expect(bouton.getAttribute("aria-label")).toMatch(new RegExp(`^${TEXTE_RELACHER}`));
  });
});
