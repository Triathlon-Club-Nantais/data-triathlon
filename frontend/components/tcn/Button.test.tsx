import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "./Button";

describe("Button", () => {
  it("porte la classe de base, la taille par défaut et le variant par défaut", () => {
    render(<Button>Filtrer</Button>);

    const bouton = screen.getByRole("button", { name: "Filtrer" });
    expect(bouton).toHaveClass("tcn-btn", "tcn-btn--md", "tcn-btn--primary");
  });

  it("décline taille et variant en classes", () => {
    render(
      <Button size="sm" variant="ghost">
        Réinitialiser
      </Button>,
    );

    const bouton = screen.getByRole("button", { name: "Réinitialiser" });
    expect(bouton).toHaveClass("tcn-btn--sm", "tcn-btn--ghost");
    expect(bouton).not.toHaveClass("tcn-btn--md", "tcn-btn--primary");
  });

  it("ajoute la classe de l'appelant au lieu de l'écraser", () => {
    // `className` arrivait par `...rest` et remplaçait le nôtre en silence.
    render(<Button className="w-full">Se connecter</Button>);

    const bouton = screen.getByRole("button", { name: "Se connecter" });
    expect(bouton).toHaveClass("tcn-btn", "tcn-btn--primary", "w-full");
  });

  it("laisse le style de l'appelant passer", () => {
    render(<Button style={{ width: "100%" }}>Se connecter</Button>);

    expect(screen.getByRole("button", { name: "Se connecter" })).toHaveStyle({ width: "100%" });
  });

  it("transmet disabled", () => {
    render(<Button disabled>Enregistrer</Button>);

    expect(screen.getByRole("button", { name: "Enregistrer" })).toBeDisabled();
  });
});
