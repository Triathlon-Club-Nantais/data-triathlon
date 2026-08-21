import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetaPill } from "./MetaPill";

describe("MetaPill", () => {
  it("rend un simple chip sans href", () => {
    const { container } = render(<MetaPill label="Date">16/05/2026</MetaPill>);
    expect(screen.getByText("16/05/2026")).toBeInTheDocument();
    expect(container.querySelector("a")).toBeNull();
  });

  it("devient un lien externe quand href est fourni", () => {
    render(
      <MetaPill label="Source" href="https://www.klikego.com/resultats/x">
        Klikego
      </MetaPill>,
    );
    const link = screen.getByRole("link", { name: /Klikego/ });
    expect(link).toHaveAttribute("href", "https://www.klikego.com/resultats/x");
    expect(link).toHaveAttribute("target", "_blank");
    // Onglet ouvert sur un site tiers : `noopener` lui coupe l'accès à window.opener.
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  // Le texte de la variante accentuée se pose **sur** de l'orange : c'est le cas
  // que la paire `-deep`/`-deeper` de #299 existe pour couvrir. `--tcn-orange`
  // n'y tenait que 3,01:1 sur le composite (`--tcn-orange-08` sur
  // `--tcn-paper` = #f3e6de), pour du 13 px gras — donc du texte courant au sens
  // WCAG, seuil 4,5:1. `--tcn-orange-deeper` le porte à 4,72:1.
  it("porte le texte accentué dans l'orange qui tient sur un fond orangé", () => {
    render(<MetaPill accent>3 athlètes TCN</MetaPill>);
    expect(screen.getByText("3 athlètes TCN").style.color).toBe("var(--tcn-orange-deeper)");
  });

  it("retombe sur un chip quand href n'est pas une URL http(s)", () => {
    const { container } = render(
      <MetaPill label="Source" href="javascript:alert(1)">
        Klikego
      </MetaPill>,
    );
    expect(container.querySelector("a")).toBeNull();
    expect(screen.getByText("Klikego")).toBeInTheDocument();
  });
});
