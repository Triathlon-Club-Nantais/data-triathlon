import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Input } from "./Input";

describe("Input — le champ au doigt (#492, ACT-5)", () => {
  it("ne fige aucune taille de police en ligne", () => {
    // La taille vit dans `.tcn-input` : 16 px sous `md` — le seuil à partir
    // duquel iOS Safari cesse de zoomer à la mise au point. Une valeur en ligne
    // rendrait la media query inerte, quelle que soit sa valeur.
    render(<Input aria-label="Adresse" />);
    expect(screen.getByLabelText("Adresse").style.fontSize).toBe("");
  });

  it("rend les actions posées dans le champ, à droite du texte", async () => {
    const onClick = vi.fn();
    render(
      <Input
        aria-label="Adresse"
        actions={<button onClick={onClick}>Coller</button>}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Coller" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
