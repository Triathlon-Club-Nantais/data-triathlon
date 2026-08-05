import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImportProgress } from "./ImportProgress";
import type { ImportState } from "@/hooks/useImportStream";

function state(overrides: Partial<ImportState>): ImportState {
  return {
    running: false, phase: "idle", message: "", total: 0, progress: 0,
    imported: 0, updated: 0, skipped: 0, cached: false, courses: [],
    heatIndex: 0, heatsScrapingTotal: 0, heatLabel: "", heatSlug: "",
    heatsEnumerated: 0, heatsImported: 0, heatsCached: 0, heatsFailed: 0, failures: [],
    error: null,
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

  // T014 — récap des courses créées (#135 + fan-out #156)
  it("ne rend aucun lien de course si courses est vide", () => {
    render(<ImportProgress state={state({ phase: "done", courses: [] })} />);
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("rend un lien pour une course unique", () => {
    const courses = [{ id: 42, name: "Triathlon de Mesquer", event_type: "triathlon-s" }];
    render(<ImportProgress state={state({ phase: "done", courses })} />);
    const link = screen.getByRole("link", { name: /Triathlon de Mesquer/ });
    expect(link.getAttribute("href")).toBe("/courses/42");
  });

  it("rend N liens pour N courses (fan-out)", () => {
    const courses = Array.from({ length: 8 }, (_, i) => ({
      id: 100 + i,
      name: `Course ${i}`,
      event_type: "triathlon-s",
    }));
    render(<ImportProgress state={state({ phase: "done", courses })} />);
    const links = screen.getAllByRole("link");
    expect(links.length).toBe(8);
    expect(links[0].getAttribute("href")).toBe("/courses/100");
    expect(links[7].getAttribute("href")).toBe("/courses/107");
  });

  // T015 — rendu des heats en échec (fan-out #156)
  it("ne rend aucun bloc d'échec si failures est vide", () => {
    render(<ImportProgress state={state({ phase: "done", failures: [] })} />);
    expect(screen.queryByText(/Heats en erreur/i)).toBeNull();
  });

  it("rend un bloc listant chaque heat en erreur avec sa cause", () => {
    const failures = [
      { heat_slug: "triathlon-xs-relais", reason: "HTTPError 502" },
      { heat_slug: "swim-run-s-duo", reason: "timeout" },
    ];
    render(<ImportProgress state={state({ phase: "done", failures, heatsFailed: 2 })} />);
    expect(screen.getByText(/Heats en erreur/i)).toBeTruthy();
    expect(screen.getByText(/triathlon-xs-relais/)).toBeTruthy();
    expect(screen.getByText(/HTTPError 502/)).toBeTruthy();
    expect(screen.getByText(/swim-run-s-duo/)).toBeTruthy();
    expect(screen.getByText(/timeout/)).toBeTruthy();
  });
});
