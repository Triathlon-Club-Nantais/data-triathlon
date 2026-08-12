import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { GeoEvent } from "@/lib/types";

const { getEventsGeo } = vi.hoisted(() => ({ getEventsGeo: vi.fn() }));
vi.mock("@/lib/api/client", async (originale) => {
  const reel = await originale<typeof import("@/lib/api/client")>();
  return { ...reel, apiClient: { getEventsGeo } };
});

// Leaflet manipule la géométrie du conteneur, que jsdom ne mesure pas. Seule la
// composition nous intéresse ici : les états, la microcopie et la liste jumelle.
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children?: React.ReactNode }) => <div data-testid="carte">{children}</div>,
  TileLayer: () => null,
  CircleMarker: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Popup: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  useMap: () => ({ fitBounds: vi.fn() }),
}));

import { LIBELLE_CHARGEMENT } from "./carte";
import { MapView } from "./MapView";

function epreuve(over: Partial<GeoEvent> = {}): GeoEvent {
  return { event_name: "Triathlon de Nantes", event_date: "2026-06-14", event_type: "triathlon", count: 320, tcn_count: 2, lat: 47.2, lon: -1.5, ...over };
}

describe("MapView", () => {
  beforeEach(() => {
    getEventsGeo.mockReset();
  });

  it("attend avec le libellé de chargement partagé par les trois niveaux", async () => {
    // L'écran en enchaînait trois différents : « Chargement… », « Chargement de
    // la carte… », « Géolocalisation des courses… ».
    getEventsGeo.mockReturnValue(new Promise(() => {}));
    render(<MapView />);

    expect(await screen.findByText(LIBELLE_CHARGEMENT)).toBeInTheDocument();
  });

  it("invite à ajouter une épreuve quand la carte est vide", async () => {
    getEventsGeo.mockResolvedValue([]);
    render(<MapView />);

    expect(await screen.findByRole("link", { name: /ajouter/i })).toHaveAttribute("href", "/ajouter");
  });

  it("dit ce qui a échoué et offre de réessayer", async () => {
    getEventsGeo.mockRejectedValueOnce(new Error("réseau"));
    render(<MapView />);

    const reessayer = await screen.findByRole("button", { name: "Réessayer" });
    expect(screen.getByText(/n'ont pas pu être chargés/)).toBeInTheDocument();

    getEventsGeo.mockResolvedValue([epreuve()]);
    await userEvent.click(reessayer);

    expect(await screen.findByTestId("carte")).toBeInTheDocument();
    expect(getEventsGeo).toHaveBeenCalledTimes(2);
  });

  it("parle d'épreuves, comme le reste de l'écran, et jamais de courses", async () => {
    getEventsGeo.mockResolvedValue([]);
    render(<MapView />);

    await screen.findByRole("link", { name: /ajouter/i });
    expect(document.body.textContent).not.toMatch(/course/i);
  });
});
