import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const push = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/club/athletes",
  useSearchParams: () => searchParams,
}));

import { AthleteSortToggle } from "./AthleteSortToggle";

let pushState: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  push.mockClear();
  searchParams = new URLSearchParams();
  pushState = vi.spyOn(window.history, "pushState").mockImplementation(() => {});
});

afterEach(() => {
  pushState.mockRestore();
});

describe("AthleteSortToggle", () => {
  it("rend les deux boutons de tri", () => {
    render(<AthleteSortToggle />);
    expect(screen.getByRole("radio", { name: "Nombre d'épreuves" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Nom de famille" })).toBeInTheDocument();
  });

  it("porte .tcn-radio-toggle (revue UI/UX #274) : l'input caché a un focus visible via :has() dans globals.css", () => {
    render(<AthleteSortToggle />);
    const option = screen.getByRole("radio", { name: "Nom de famille" }).closest("label");
    expect(option?.className).toContain("tcn-radio-toggle");
  });

  it("sans paramètre URL, « Nombre d'épreuves » est actif (défaut)", () => {
    render(<AthleteSortToggle />);
    expect(screen.getByRole("radio", { name: "Nombre d'épreuves" })).toBeChecked();
  });

  it("?sort=nom → « Nom de famille » actif", () => {
    searchParams = new URLSearchParams("sort=nom");
    render(<AthleteSortToggle />);
    expect(screen.getByRole("radio", { name: "Nom de famille" })).toBeChecked();
  });

  it("clic sur « Nom de famille » → pushState avec ?sort=nom, sans navigation", () => {
    render(<AthleteSortToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Nom de famille" }));
    expect(pushState).toHaveBeenCalledWith(null, "", "/club/athletes?sort=nom");
    expect(push).not.toHaveBeenCalled();
  });

  it("clic sur le défaut depuis un autre tri → retire le paramètre", () => {
    searchParams = new URLSearchParams("sort=nom");
    render(<AthleteSortToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Nombre d'épreuves" }));
    expect(pushState).toHaveBeenCalledWith(null, "", "/club/athletes");
  });

  it("compose avec les autres paramètres sans les écraser", () => {
    searchParams = new URLSearchParams("seasons=2025");
    render(<AthleteSortToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Nom de famille" }));
    const url = pushState.mock.calls[0][2] as string;
    expect(url).toContain("sort=nom");
    expect(url).toContain("seasons=2025");
  });
});
