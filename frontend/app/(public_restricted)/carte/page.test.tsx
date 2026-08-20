import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// `MapView` est un composant client lourd (Leaflet, fetch) sans rapport avec
// ce qui est testé ici — la scission de la frontière `Suspense`, pas le rendu
// de la carte elle-même. La timing réelle de `Suspense` (le titre qui peint
// avant la carte) ne s'observe pas en jsdom, où `next/dynamic` résout tout de
// façon synchrone quel que soit le découpage des frontières ; elle se
// vérifie par lecture du HTML servi (voir la revue manuelle de la PR).
vi.mock("@/components/map/MapView", () => ({
  MapView: () => <div data-testid="map-view">carte</div>,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/carte",
}));

import CartePage from "./page";

describe("CartePage", () => {
  it("rend le titre et la bascule de portée sans attendre le chargement du chunk carte", () => {
    // `MapView` est chargé via `next/dynamic({ssr:false})`, un import
    // asynchrone même une fois mocké : `render()` ne le résout pas tout seul.
    // Le titre, lui, ne doit dépendre d'aucune résolution asynchrone.
    render(<CartePage />);

    expect(screen.getByText("Carte des épreuves")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Portée" })).toBeInTheDocument();
  });

  it("rend la carte une fois son chunk résolu", async () => {
    render(<CartePage />);

    expect(await screen.findByTestId("map-view")).toBeInTheDocument();
  });
});
