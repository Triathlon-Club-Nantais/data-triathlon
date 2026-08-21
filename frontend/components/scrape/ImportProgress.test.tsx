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
    // La région sr-only (#477) répète le même récapitulatif : on cible le
    // paragraphe visible pour ne pas matcher les deux à la fois.
    const recap = screen.getByText(/4 ajoutés/, { selector: "p.text-success" });
    expect(recap).toHaveTextContent("2 mis à jour");
    expect(recap).toHaveTextContent("4 ignorés");
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

  it("affiche le type d'épreuve via eventTypeLabel plutôt que le code brut", () => {
    const courses = [{ id: 42, name: "Triathlon de Mesquer", event_type: "triathlon-s" }];
    render(<ImportProgress state={state({ phase: "done", courses })} />);
    expect(screen.getByText("Triathlon S")).toBeInTheDocument();
    expect(screen.queryByText("triathlon-s")).not.toBeInTheDocument();
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
    expect(screen.queryByText(/n'a pas pu être importée|n'ont pas pu être importées/i)).toBeNull();
  });

  it("rend un bloc en français métier listant chaque série en erreur avec sa cause, sans le slug technique", () => {
    const failures = [
      { heat_slug: "triathlon-xs-relais", reason: "HTTPError 502" },
      { heat_slug: "swim-run-s-duo", reason: "timeout" },
    ];
    render(<ImportProgress state={state({ phase: "done", failures, heatsFailed: 2 })} />);
    expect(screen.getByText("2 séries n'ont pas pu être importées :")).toBeTruthy();
    expect(screen.queryByText(/Heats en erreur/i)).toBeNull();
    expect(screen.queryByText(/triathlon-xs-relais/)).toBeNull();
    expect(screen.queryByText(/swim-run-s-duo/)).toBeNull();
    expect(screen.getByText(/HTTPError 502/)).toBeTruthy();
    expect(screen.getByText(/timeout/)).toBeTruthy();
  });

  // ── Annonce jalonnée (WCAG 4.1.3, #477) ────────────────────────────────────
  // L'import SSE est l'opération la plus longue de l'app et n'avait aucun
  // annonceur : `aria-live="polite"` + `aria-busy`, jalonné par quart de
  // progression plutôt qu'à chaque message SSE (sinon le flux spamme un
  // lecteur d'écran).

  it("ne rend aucune région de statut en idle", () => {
    render(<ImportProgress state={state({ phase: "idle" })} />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("porte aria-busy pendant la récupération des participants", () => {
    render(<ImportProgress state={state({ phase: "scraping", message: "Récupération des participants…" })} />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveTextContent("Récupération des participants");
  });

  it("ne réannonce pas à chaque message SSE dans le même quart de progression", () => {
    const { rerender } = render(
      <ImportProgress state={state({ phase: "saving", total: 10, progress: 1, imported: 1, updated: 0, skipped: 0 })} />,
    );
    const texteInitial = screen.getByRole("status").textContent;

    rerender(
      <ImportProgress state={state({ phase: "saving", total: 10, progress: 2, imported: 2, updated: 0, skipped: 0 })} />,
    );

    expect(screen.getByRole("status").textContent).toBe(texteInitial);
  });

  it("réannonce au franchissement d'un quart de progression", () => {
    const { rerender } = render(
      <ImportProgress state={state({ phase: "saving", total: 10, progress: 1, imported: 1, updated: 0, skipped: 0 })} />,
    );
    const texteInitial = screen.getByRole("status").textContent;

    rerender(
      <ImportProgress state={state({ phase: "saving", total: 10, progress: 3, imported: 3, updated: 0, skipped: 0 })} />,
    );

    expect(screen.getByRole("status").textContent).not.toBe(texteInitial);
  });

  it("aria-busy retombe à la fin de l'import", () => {
    render(<ImportProgress state={state({ phase: "done", imported: 4, updated: 2, skipped: 1 })} />);
    expect(screen.getByRole("status")).not.toHaveAttribute("aria-busy", "true");
  });

  it("annonce l'erreur, sans aria-busy", () => {
    render(<ImportProgress state={state({ phase: "error", error: "Chronométreur injoignable" })} />);
    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("Chronométreur injoignable");
    expect(region).not.toHaveAttribute("aria-busy", "true");
  });

  it("accorde le message au singulier pour une seule série en échec", () => {
    const failures = [{ heat_slug: "triathlon-xs-relais", reason: "HTTPError 502" }];
    render(<ImportProgress state={state({ phase: "done", failures, heatsFailed: 1 })} />);
    expect(screen.getByText("1 série n'a pas pu être importée :")).toBeTruthy();
  });
});
