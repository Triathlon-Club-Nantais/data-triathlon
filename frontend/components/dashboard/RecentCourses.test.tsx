import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { EventOut } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({
    href,
    prefetch,
    children,
    ...rest
  }: {
    href: string;
    prefetch?: boolean;
    children?: ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} data-prefetch={String(prefetch)} {...rest}>
      {children}
    </a>
  ),
}));

import { RecentCourses } from "./RecentCourses";

const EVENT: EventOut = {
  id: 5,
  event_name: "Ironman Nantes",
  event_date: "2026-06-14",
  event_type: "Triathlon L",
  is_relay: false,
  distance_km: 113,
  total: 30,
  tcn_count: 5,
};

describe("RecentCourses", () => {
  it("rend la date, le nom et le lien de chaque épreuve, sans prefetch (#425)", () => {
    render(<RecentCourses events={[EVENT]} />);

    expect(screen.getByRole("heading", { level: 2, name: "Dernières épreuves" })).toBeInTheDocument();
    expect(screen.getByText("14/06/2026")).toBeInTheDocument();
    const lien = screen.getByRole("link", { name: /Ironman Nantes/ });
    expect(lien).toHaveAttribute("href", "/courses/5");
    expect(lien).toHaveAttribute("data-prefetch", "false");
  });

  it("suffixe (Relais) quand l'épreuve est un relais", () => {
    render(<RecentCourses events={[{ ...EVENT, is_relay: true }]} />);
    expect(screen.getByText("Ironman Nantes (Relais)")).toBeInTheDocument();
  });

  it("affiche un tiret quand l'épreuve n'a pas de date", () => {
    render(<RecentCourses events={[{ ...EVENT, event_date: null }]} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("affiche un état vide avec un CTA vers /ajouter quand la liste est vide", () => {
    render(<RecentCourses events={[]} />);
    expect(screen.getByText("Aucune épreuve récente à afficher")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ajouter une épreuve/ })).toHaveAttribute("href", "/ajouter");
  });

  // ── Structure de tableau (#481, A11Y-3) ────────────────────────────────────

  it("s'annonce comme un tableau et nomme ses quatre colonnes", () => {
    render(<RecentCourses events={[EVENT]} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    for (const nom of ["Date", "Épreuve", "Format", "Dossards"]) {
      expect(screen.getByRole("columnheader", { name: nom })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("row")).toHaveLength(2);
  });

  it("n'offre qu'un arrêt clavier par ligne", () => {
    // FR-011, compté **par `<tr>`** : un `href` par cellule quadruplerait les
    // tabulations sans qu'aucune autre assertion ne bronche.
    render(<RecentCourses events={[EVENT]} />);

    const ligne = screen.getAllByRole("row")[1];
    expect(ligne.querySelectorAll("a[href], button, input, select, textarea")).toHaveLength(1);
  });

  it("ne rend aucun tableau quand la liste est vide : cette carte masque déjà son en-tête", () => {
    render(<RecentCourses events={[]} />);

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
