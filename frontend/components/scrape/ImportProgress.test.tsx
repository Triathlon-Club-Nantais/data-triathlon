import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImportProgress } from "./ImportProgress";
import type { ImportState } from "@/hooks/useImportStream";

function state(overrides: Partial<ImportState>): ImportState {
  return {
    running: false, phase: "idle", message: "", total: 0, progress: 0,
    imported: 0, updated: 0, skipped: 0, cached: false, error: null,
    ...overrides,
  };
}

describe("ImportProgress", () => {
  it("affiche les trois compteurs pendant l'enregistrement", () => {
    render(<ImportProgress state={state({ phase: "saving", total: 10, progress: 6, imported: 4, updated: 2, skipped: 1 })} />);
    expect(screen.getByText(/4 ajoutés/)).toBeTruthy();
    expect(screen.getByText(/2 mis à jour/)).toBeTruthy();
    expect(screen.getByText(/1 ignorés/)).toBeTruthy();
  });

  it("récapitule les trois compteurs à la fin", () => {
    render(<ImportProgress state={state({ phase: "done", total: 10, progress: 10, imported: 4, updated: 2, skipped: 4 })} />);
    expect(screen.getByText(/4 ajoutés/)).toBeTruthy();
    expect(screen.getByText(/2 mis à jour/)).toBeTruthy();
    expect(screen.getByText(/4 ignorés/)).toBeTruthy();
  });
});
