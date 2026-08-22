import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SegmentedControl } from "./SegmentedControl";

describe("SegmentedControl", () => {
  it("porte la classe tcn-segmented-btn, seule à exprimer :focus-visible (#342)", () => {
    // Le composant est 100 % en style inline : sans classe, `:focus-visible`
    // est inexprimable et le focus retombe sur l'anneau universel à 1,86:1
    // (`outline-ring/50`, sous le seuil WCAG 1.4.11 de 3:1).
    render(<SegmentedControl value="a" onChange={() => {}} options={["a", "b"]} />);
    expect(screen.getByRole("button", { name: "a" })).toHaveClass("tcn-segmented-btn");
    expect(screen.getByRole("button", { name: "b" })).toHaveClass("tcn-segmented-btn");
  });

  it("porte aria-pressed reflétant l'option active", () => {
    // Précédent : `ScopeToggle`. Un lecteur d'écran doit pouvoir annoncer
    // l'état sélectionné même si le conteneur n'est pas un radiogroup.
    render(<SegmentedControl value="b" onChange={() => {}} options={["a", "b"]} />);
    expect(screen.getByRole("button", { name: "a" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "b" })).toHaveAttribute("aria-pressed", "true");
  });

  it("appelle onChange avec la valeur cliquée", () => {
    const onChange = vi.fn();
    render(<SegmentedControl value="a" onChange={onChange} options={["a", "b"]} />);
    fireEvent.click(screen.getByRole("button", { name: "b" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("rend l'option active en tone=\"orange\" avec --tcn-orange-deeper, seul à tenir 4,5:1 (revue UI/UX #465)", () => {
    // --tcn-orange ne tient que 3,25:1 à 13-14px — sous le seuil AA.
    render(<SegmentedControl value="a" onChange={() => {}} tone="orange" options={["a", "b"]} />);
    expect(screen.getByRole("button", { name: "a" }).style.color).toBe("var(--tcn-orange-deeper)");
  });

  it("accepte des options objet avec label distinct de la valeur", () => {
    render(
      <SegmentedControl
        value="tcn"
        onChange={() => {}}
        options={[
          { value: "all", label: "Tous les coureurs (42)" },
          { value: "tcn", label: "TCN (7)", dot: true },
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: "Tous les coureurs (42)" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "TCN (7)" })).toHaveAttribute("aria-pressed", "true");
  });
});
