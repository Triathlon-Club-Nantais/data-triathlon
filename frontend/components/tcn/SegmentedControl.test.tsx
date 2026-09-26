import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("gives each segment the public touch target, 44 px below md (#479, #1079)", () => {
    // Le plancher vit dans `.tcn-cible-tactile` (globals.css) : un
    // `minHeight` en ligne l'emporterait sur la media query.
    render(<SegmentedControl value="a" onChange={() => {}} options={["a", "b"]} />);
    const segment = screen.getByRole("button", { name: "a" });
    expect(segment).toHaveClass("tcn-cible-tactile");
    expect(segment.style.minHeight).toBe("");
  });

  it("n'appelle pas onChange sur une option désactivée", async () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        value="all"
        onChange={onChange}
        options={[
          { value: "all", label: "Tous" },
          { value: "tcn", label: "TCN", disabled: true },
        ]}
      />,
    );

    const tcn = screen.getByRole("button", { name: "TCN" });
    expect(tcn).toHaveAttribute("aria-disabled", "true");

    await userEvent.click(tcn);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("rend un segment désactivé en --tcn-text-faint plutôt qu'en opacité (revue UI/UX #485)", () => {
    // `opacity: 0.5` rendait le texte à 2,75:1 sur blanc, sous le seuil WCAG
    // 1.4.3 — contradictoire avec l'information que le segment porte encore
    // via `aria-disabled`. `--tcn-text-faint` seul tient 5,21:1.
    render(
      <SegmentedControl
        value="all"
        onChange={() => {}}
        options={[
          { value: "all", label: "Tous" },
          { value: "tcn", label: "TCN", disabled: true },
        ]}
      />,
    );

    const tcn = screen.getByRole("button", { name: "TCN" });
    expect(tcn.style.opacity).toBe("");
    expect(tcn.style.color).toBe("var(--tcn-text-faint)");
  });

  it("garde le contraste de l'état actif sur un segment à la fois actif et désactivé (re-revue #485)", () => {
    // `/courses/42?scope=club` sur une épreuve sans athlète club : `value`
    // (l'URL) et `disabled` (le compte TCN) sont calculés indépendamment,
    // rien n'empêche les deux à la fois. `--tcn-text-faint` sur `--tcn-ink`
    // ne tient que 3,21:1 — le blanc actif (16,15:1) doit rester intact.
    render(
      <SegmentedControl
        value="tcn"
        onChange={() => {}}
        options={[
          { value: "all", label: "Tous" },
          { value: "tcn", label: "TCN", disabled: true },
        ]}
      />,
    );

    const tcn = screen.getByRole("button", { name: "TCN" });
    expect(tcn.style.color).toBe("rgb(255, 255, 255)");
  });
});
