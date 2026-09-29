import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { contrast, resolve } from "@/test/couleur";

const { recu } = vi.hoisted(() => ({
  recu: {
    style: {} as Record<string, string>,
    classNames: {} as Record<string, string>,
  },
}));
vi.mock("sonner", () => ({
  Toaster: (props: { style: Record<string, string>; toastOptions: { classNames: Record<string, string> } }) => {
    recu.style = props.style;
    recu.classNames = props.toastOptions.classNames;
    return null;
  },
}));

import { Toaster } from "./sonner";

const VARIANTES = ["success", "error", "warning"] as const;

function tokenDe(valeur: string): string {
  const nom = /^var\((--[\w-]+)\)$/.exec(valeur)?.[1];
  if (!nom) throw new Error(`not a var(): ${valeur}`);
  return nom;
}

describe("Toaster rich colors (#1030)", () => {
  it.each(VARIANTES)("maps the %s variant to TCN semantic tokens at AA contrast", (variante) => {
    render(<Toaster />);

    const texte = recu.style[`--${variante}-text`];
    const fond = recu.style[`--${variante}-bg`];
    expect(texte).toMatch(/^var\(--tcn-/);
    expect(fond).toMatch(/^var\(--tcn-/);
    expect(recu.style[`--${variante}-border`]).toMatch(/^var\(--tcn-/);
    expect(contrast(resolve(tokenDe(texte)), resolve(tokenDe(fond)))).toBeGreaterThanOrEqual(4.5);
  });
});

// #1062 : le bouton d'action d'un toast est parfois le seul chemin vers le
// bilan d'un import ; sous `md`, il porte une cible de 44 px.
describe("Toaster touch targets (#1062)", () => {
  it("gives action and cancel buttons a 44 px minimum height below md", () => {
    render(<Toaster />);

    expect(recu.classNames.actionButton).toContain("max-md:min-h-11");
    expect(recu.classNames.cancelButton).toContain("max-md:min-h-11");
  });
});
