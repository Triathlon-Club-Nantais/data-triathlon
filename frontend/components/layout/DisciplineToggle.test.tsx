import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const push = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => searchParams,
}));

import { DisciplineToggle } from "./DisciplineToggle";

beforeEach(() => {
  push.mockClear();
  searchParams = new URLSearchParams();
});

describe("DisciplineToggle", () => {
  it("compose avec les autres paramètres serveur sans les écraser", () => {
    searchParams = new URLSearchParams("seasons=2025-2026");
    render(<DisciplineToggle />);
    fireEvent.click(screen.getByRole("checkbox"));
    const url = push.mock.calls[0][0] as string;
    expect(url).toContain("sports=all");
    expect(url).toContain("seasons=2025-2026");
  });

  it("ne propage pas ?rank= dans la navigation — c'est un paramètre strictement client (#328), aucun rendu serveur ne le lit", () => {
    // Régression #425 : DisciplineToggle clonait tout `sp.toString()`, donc
    // `?rank=` survivait au `router.push` et déclenchait un aller-retour RSC
    // pour une valeur que le serveur ignore totalement — un fetch storm pour
    // rien à chaque bascule scratch/catégorie/genre/tous.
    searchParams = new URLSearchParams("rank=gender");
    render(<DisciplineToggle />);
    fireEvent.click(screen.getByRole("checkbox"));
    const url = push.mock.calls[0][0] as string;
    expect(url).not.toContain("rank=");
  });
});
