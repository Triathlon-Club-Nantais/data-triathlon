import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const push = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => searchParams,
}));

import { RankTypeToggle } from "./RankTypeToggle";

beforeEach(() => {
  push.mockClear();
  searchParams = new URLSearchParams();
});

describe("RankTypeToggle", () => {
  it("rend les 4 boutons canoniques (Général, Catégorie, Genre, Tous)", () => {
    render(<RankTypeToggle />);
    expect(screen.getByRole("radio", { name: "Général" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Catégorie" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Genre" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Tous" })).toBeInTheDocument();
  });

  it("sans paramètre URL, le bouton Général est actif (défaut)", () => {
    render(<RankTypeToggle />);
    expect(screen.getByRole("radio", { name: "Général" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Catégorie" })).not.toBeChecked();
  });

  it("?rank=category → Catégorie actif", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<RankTypeToggle />);
    expect(screen.getByRole("radio", { name: "Catégorie" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Général" })).not.toBeChecked();
  });

  it("?rank=foo (valeur inconnue) → Général actif (défaut silencieux)", () => {
    searchParams = new URLSearchParams("rank=foo");
    render(<RankTypeToggle />);
    expect(screen.getByRole("radio", { name: "Général" })).toBeChecked();
  });

  it("clic sur Genre → push /dashboard?rank=gender", () => {
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Genre" }));
    expect(push).toHaveBeenCalledWith("/dashboard?rank=gender");
  });

  it("clic sur Général depuis Catégorie → retire le paramètre (défaut implicite)", () => {
    // On préfère nettoyer l'URL quand on retombe sur le défaut, plutôt que de
    // laisser un ?rank=scratch redondant traîner. Deux liens différents pour
    // une même vue nuisent au partage.
    searchParams = new URLSearchParams("rank=category");
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Général" }));
    expect(push).toHaveBeenCalledWith("/dashboard");
  });

  it("compose avec les autres paramètres sans les écraser", () => {
    searchParams = new URLSearchParams("seasons=2025-2026&sports=all");
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Catégorie" }));
    const call = push.mock.calls[0][0] as string;
    expect(call).toContain("rank=category");
    expect(call).toContain("seasons=2025-2026");
    expect(call).toContain("sports=all");
  });
});
