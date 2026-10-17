import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChiffreAnime } from "./ChiffreAnime";

function reducedMotion(matches: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches, media: query, addEventListener() {}, removeEventListener() {} }));
}

describe("ChiffreAnime", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the final value straight away under reduced motion", () => {
    reducedMotion(true);
    render(<ChiffreAnime valeur={1234} />);
    expect(screen.getByText(/^1\s234$/)).toBeInTheDocument();
  });

  it("exposes the final value to assistive tech while it animates", () => {
    reducedMotion(false);
    let premier = true;
    vi.stubGlobal("requestAnimationFrame", (rappel: FrameRequestCallback) => {
      if (premier) {
        premier = false;
        rappel(0);
      }
      return 1;
    });
    render(<ChiffreAnime valeur={48} />);
    expect(screen.getByText("48", { selector: ".sr-only" })).toBeInTheDocument();
  });
});
