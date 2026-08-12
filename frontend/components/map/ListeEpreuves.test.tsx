import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { GeoEvent } from "@/lib/types";
import { ListeEpreuves } from "./ListeEpreuves";

function epreuve(over: Partial<GeoEvent> = {}): GeoEvent {
  return { event_name: "Triathlon de Nantes", event_date: "2026-06-14", event_type: "triathlon", count: 320, tcn_count: 0, lat: 47.2, lon: -1.5, ...over };
}

describe("ListeEpreuves", () => {
  it("double la carte d'une ligne par épreuve", () => {
    // WCAG 2.1.1 — Leaflet ne rend focusables que les `L.Marker`, jamais les
    // couches vectorielles : sans cette liste, 0 % du contenu de la carte est
    // atteignable au clavier.
    render(<ListeEpreuves events={[epreuve(), epreuve({ event_name: "Trail des Ardennes" })]} />);

    expect(screen.getByRole("row", { name: /Triathlon de Nantes/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Trail des Ardennes/ })).toBeInTheDocument();
  });

  it("dit la présence de membres en mots, pas seulement par la couleur du cercle", () => {
    // WCAG 1.4.1 — sur la carte, TCN et non-TCN ne se distinguaient que par le
    // remplissage.
    render(<ListeEpreuves events={[epreuve({ tcn_count: 3 }), epreuve({ event_name: "Trail", tcn_count: 0 })]} />);

    expect(screen.getByRole("row", { name: /3 membres/ })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /aucun membre/i })).toBeInTheDocument();
  });

  it("annonce le nombre d'épreuves sur le résumé dépliable", () => {
    render(<ListeEpreuves events={[epreuve(), epreuve({ event_name: "Trail" })]} />);

    expect(screen.getByText(/2 épreuves/)).toBeInTheDocument();
  });

  it("ne rend rien sans épreuve", () => {
    const { container } = render(<ListeEpreuves events={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
