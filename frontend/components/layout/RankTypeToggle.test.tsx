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

// `SegmentedControl` (#342) pose l'état actif en encre sur blanc, pas via
// `aria-checked` — la sélection s'y vérifie donc par le style, pas par
// `toBeChecked()` (qui n'a de sens que pour un input radio natif).
function isActive(button: HTMLElement) {
  return button.style.background === "var(--tcn-ink)" && button.style.color === "rgb(255, 255, 255)";
}

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
    expect(screen.getByRole("button", { name: "Général" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Catégorie" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Genre" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tous" })).toBeInTheDocument();
  });

  it("le groupe porte le rôle group (pas radiogroup — ses enfants sont des boutons, pas des radios) et son libellé", () => {
    render(<RankTypeToggle />);
    expect(screen.getByRole("group", { name: "Type de rang" })).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });

  it("aria-pressed reflète l'option active, pas seulement le style", () => {
    render(<RankTypeToggle />);
    expect(screen.getByRole("button", { name: "Général" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Catégorie" })).toHaveAttribute("aria-pressed", "false");
  });

  it("sans paramètre URL, le bouton Général est actif (défaut)", () => {
    render(<RankTypeToggle />);
    expect(isActive(screen.getByRole("button", { name: "Général" }))).toBe(true);
    expect(isActive(screen.getByRole("button", { name: "Catégorie" }))).toBe(false);
  });

  it("?rank=category → Catégorie actif", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<RankTypeToggle />);
    expect(isActive(screen.getByRole("button", { name: "Catégorie" }))).toBe(true);
    expect(isActive(screen.getByRole("button", { name: "Général" }))).toBe(false);
  });

  it("?rank=foo (valeur inconnue) → Général actif (défaut silencieux)", () => {
    searchParams = new URLSearchParams("rank=foo");
    render(<RankTypeToggle />);
    expect(isActive(screen.getByRole("button", { name: "Général" }))).toBe(true);
  });

  it("clic sur Genre → l'URL passe à ?rank=gender par l'historique, sans navigation", () => {
    // Aucun rendu serveur ne lit `?rank=` : les trois consommateurs le relisent
    // par `useSearchParams` et recalculent en mémoire. Un `router.push` rejouait
    // donc tout le rendu de /dashboard — dont `listEvents(page_size: 200)`,
    // `getStats` et `listSeasons` — pour un résultat que le client tenait
    // déjà (#328).
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Genre" }));
    expect(pushState).toHaveBeenCalledWith(null, "", "/dashboard?rank=gender");
    expect(push).not.toHaveBeenCalled();
  });

  it("clic sur Général depuis Catégorie → retire le paramètre (défaut implicite)", () => {
    // On préfère nettoyer l'URL quand on retombe sur le défaut, plutôt que de
    // laisser un ?rank=scratch redondant traîner. Deux liens différents pour
    // une même vue nuisent au partage.
    searchParams = new URLSearchParams("rank=category");
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Général" }));
    expect(pushState).toHaveBeenCalledWith(null, "", "/dashboard");
    expect(push).not.toHaveBeenCalled();
  });

  it("compose avec les autres paramètres sans les écraser", () => {
    searchParams = new URLSearchParams("seasons=2025-2026&sports=all");
    render(<RankTypeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Catégorie" }));
    const url = pushState.mock.calls[0][2] as string;
    expect(url).toContain("rank=category");
    expect(url).toContain("seasons=2025-2026");
    expect(url).toContain("sports=all");
  });
});
