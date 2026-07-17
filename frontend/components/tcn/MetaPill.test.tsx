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
});
