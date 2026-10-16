import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Histogram, isMarkerInRange } from "./Histogram";

// Épreuve de 2h, 4 tranches de 30 min : [0, 30, 60, 90] min.
const bars = [3, 8, 5, 1];
const startSec = 0;
const bucketSec = 30 * 60;

describe("Histogram — repère de l'athlète (US2, #466)", () => {
  it("sans markerSec, ne rend aucun repère (comportement existant préservé)", () => {
    const { container } = render(
      <Histogram bars={bars} max={8} startSec={startSec} bucketSec={bucketSec} />
    );
    expect(container.querySelector("[data-athlete-marker]")).toBeNull();
  });

  it("avec markerSec dans la fenêtre, rend un repère visuel", () => {
    const { container } = render(
      <Histogram
        bars={bars}
        max={8}
        startSec={startSec}
        bucketSec={bucketSec}
        markerSec={45 * 60} // tombe dans la 2e tranche [30, 60)
      />
    );
    expect(container.querySelector("[data-athlete-marker]")).not.toBeNull();
  });

  it("avec markerSec hors de la fenêtre des tranches, ne rend aucun repère", () => {
    const { container } = render(
      <Histogram
        bars={bars}
        max={8}
        startSec={startSec}
        bucketSec={bucketSec}
        markerSec={999 * 60}
      />
    );
    expect(container.querySelector("[data-athlete-marker]")).toBeNull();
  });

  it("le résumé accessible mentionne la position de l'athlète quand un repère est fourni", () => {
    const { container } = render(
      <Histogram
        bars={bars}
        max={8}
        startSec={startSec}
        bucketSec={bucketSec}
        markerSec={45 * 60}
      />
    );
    const summary = container.querySelector("[role='img']")?.getAttribute("aria-label");
    expect(summary).toMatch(/le temps de l'athlète/i);
    expect(summary).not.toMatch(/votre/i);
  });
});

describe("isMarkerInRange (#1586)", () => {
  it("vrai dans la fenêtre des tranches, bord droit compris", () => {
    expect(isMarkerInRange(45 * 60, bars.length, startSec, bucketSec)).toBe(true);
    expect(isMarkerInRange(120 * 60, bars.length, startSec, bucketSec)).toBe(true);
  });

  it("faux hors fenêtre, sans temps ou sans barre", () => {
    expect(isMarkerInRange(999 * 60, bars.length, startSec, bucketSec)).toBe(false);
    expect(isMarkerInRange(null, bars.length, startSec, bucketSec)).toBe(false);
    expect(isMarkerInRange(45 * 60, 0, startSec, bucketSec)).toBe(false);
  });
});
