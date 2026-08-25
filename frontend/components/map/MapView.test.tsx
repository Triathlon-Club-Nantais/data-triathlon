import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
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
  useMap: () => ({ fitBounds: vi.fn(), dragging: { enable: vi.fn(), disable: vi.fn() } }),
}));

import { LIBELLE_CHARGEMENT } from "./carte";
import { MapView, rayonCercle } from "./MapView";

function pointeurGrossier() {
  const matchMedia = vi.fn().mockReturnValue({ matches: true });
  vi.stubGlobal("matchMedia", matchMedia);
  return matchMedia;
}

describe("rayonCercle", () => {
  it("ne descend jamais sous 12 px — 24 px de diamètre, le plancher tactile WCAG 2.2 2.5.8 (#479)", () => {
    expect(rayonCercle(1, 1000)).toBeGreaterThanOrEqual(12);
  });

  it("reste borné à 40 px pour la plus grosse épreuve", () => {
    expect(rayonCercle(1000, 1000)).toBe(40);
  });
});

function epreuve(over: Partial<GeoEvent> = {}): GeoEvent {
  return { course_id: 42, event_name: "Triathlon de Nantes", event_date: "2026-06-14", event_type: "triathlon", count: 320, tcn_count: 2, lat: 47.2, lon: -1.5, ...over };
}

describe("MapView", () => {
  beforeEach(() => {
    getEventsGeo.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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

  it("le nom de l'épreuve, dans la popup, mène à sa fiche", async () => {
    // La liste de repli porte le même lien (#495 volet 2) — les deux existent.
    getEventsGeo.mockResolvedValue([epreuve({ course_id: 42 })]);
    render(<MapView />);

    const carte = await screen.findByTestId("carte");
    expect(within(carte).getByRole("link", { name: "Triathlon de Nantes" })).toHaveAttribute(
      "href",
      "/courses/42",
    );
  });

  it("sur pointeur grossier, exige un geste délibéré avant de glisser la carte", async () => {
    // ACT-10 (1) : un doigt posé pour défiler la page déplaçait la carte à la
    // place — piège de défilement classique (WCAG 2.2 2.5.7).
    pointeurGrossier();
    getEventsGeo.mockResolvedValue([epreuve()]);
    render(<MapView />);
    await screen.findByTestId("carte");

    const voile = screen.getByRole("button", { name: "Toucher pour activer la carte" });
    await userEvent.click(voile);

    expect(screen.queryByRole("button", { name: "Toucher pour activer la carte" })).not.toBeInTheDocument();
  });

  it("sur pointeur fin, ne pose aucun voile", async () => {
    getEventsGeo.mockResolvedValue([epreuve()]);
    render(<MapView />);

    await screen.findByTestId("carte");
    expect(screen.queryByRole("button", { name: "Toucher pour activer la carte" })).not.toBeInTheDocument();
  });
});
