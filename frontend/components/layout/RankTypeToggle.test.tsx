import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const push = vi.fn();
let searchParams = new URLSearchParams();

// `useRouter` reste moqué alors que le composant ne s'en sert plus : c'est ce
// qui permet d'affirmer qu'aucune navigation n'est déclenchée (#328).
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => searchParams,
}));

import { RankTypeToggle } from "./RankTypeToggle";

let pushState: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  push.mockClear();
  searchParams = new URLSearchParams();
  // Avec implémentation neutre : sans elle, le vrai `pushState` s'exécute et
  // chaque test laisse l'URL de jsdom déplacée pour le suivant.
  pushState = vi.spyOn(window.history, "pushState").mockImplementation(() => {});
});

afterEach(() => {
  pushState.mockRestore();
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

  it("clic sur Genre → l'URL passe à ?rank=gender par l'historique, sans navigation", () => {
    // Aucun rendu serveur ne lit `?rank=` : les trois consommateurs le relisent
    // par `useSearchParams` et recalculent en mémoire. Un `router.push` rejouait
    // donc tout le rendu de /dashboard — dont `listParticipations(5000)` — pour
    // un résultat que le client tenait déjà (#328).
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Genre" }));
    expect(pushState).toHaveBeenCalledWith(null, "", "/dashboard?rank=gender");
    expect(push).not.toHaveBeenCalled();
  });

  it("clic sur Général depuis Catégorie → retire le paramètre (défaut implicite)", () => {
    // On préfère nettoyer l'URL quand on retombe sur le défaut, plutôt que de
    // laisser un ?rank=scratch redondant traîner. Deux liens différents pour
    // une même vue nuisent au partage.
    searchParams = new URLSearchParams("rank=category");
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Général" }));
    expect(pushState).toHaveBeenCalledWith(null, "", "/dashboard");
    expect(push).not.toHaveBeenCalled();
  });

  it("compose avec les autres paramètres sans les écraser", () => {
    searchParams = new URLSearchParams("seasons=2025-2026&sports=all");
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: "Catégorie" }));
    const url = pushState.mock.calls[0][2] as string;
    expect(url).toContain("rank=category");
    expect(url).toContain("seasons=2025-2026");
    expect(url).toContain("sports=all");
  });
});
