import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClaimKind } from "./ClaimKind";

describe("ClaimKind", () => {
  it.each([
    ["record", "Fiche entière"],
    ["result", "Un résultat"],
    ["team", "Résultat d'équipe"],
  ] as const)("affiche la sorte %s", (kind, label) => {
    render(<ClaimKind kind={kind} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
