import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { contrast, resolve } from "@/test/couleur";

const { recu } = vi.hoisted(() => ({ recu: { style: {} as Record<string, string> } }));
vi.mock("sonner", () => ({
  Toaster: (props: { style: Record<string, string> }) => {
    recu.style = props.style;
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
