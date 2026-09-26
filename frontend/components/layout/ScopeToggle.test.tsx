import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/resultats",
}));

import { ScopeToggle } from "./ScopeToggle";

describe("ScopeToggle", () => {
  it("gives both segments the public touch target below md (#1079)", () => {
    render(<ScopeToggle />);

    for (const segment of screen.getAllByRole("button")) {
      expect(segment).toHaveClass("tcn-cible-tactile");
    }
  });
});
