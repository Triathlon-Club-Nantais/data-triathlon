import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Stats } from "@/lib/types";
import { BandeauDirect } from "./BandeauDirect";

const bucket = { victories: 0, podiums: 0, top10: 0 };
const STATS: Stats = {
  total: 312, athletes: 87, events: 14, by_type: {}, recent: [],
  by_month: { "2026-09": 120, "2026-10": 192 },
  rank_counters: { scratch: bucket, category: bucket, all: { ...bucket, podiums: 27 }, gender: { women: bucket, men: bucket } },
};
const TODAY = new Date("2026-10-15T12:00:00");

describe("BandeauDirect", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: true, media: query, addEventListener() {}, removeEventListener() {} }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows a recent outing as « Ce week-end » with its figures", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={{ end_date: "2026-10-11", events: 3, athletes: 48, podiums: 9, courses: [] }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByText("Ce week-end")).toBeInTheDocument();
    expect(screen.getByText("48 TCN")).toBeInTheDocument();
    expect(screen.getByText(/3 épreuves · 9 podiums/)).toBeInTheDocument();
  });

  it("pulses next to « Ce week-end » only for a very recent outing", () => {
    const { container, rerender } = render(<BandeauDirect resultatsHref="/resultats" sortie={{ end_date: "2026-10-14", events: 1, athletes: 5, podiums: 0, courses: [] }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(container.querySelector(".tcn-pouls")).toHaveAttribute("aria-hidden", "true");
    rerender(<BandeauDirect resultatsHref="/resultats" sortie={{ end_date: "2026-10-10", events: 1, athletes: 5, podiums: 0, courses: [] }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(container.querySelector(".tcn-pouls")).toBeNull();
  });

  it("indexes each histogram bar for the staggered growth", () => {
    const { container } = render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    const barres = [...container.querySelectorAll(".tcn-barre")];
    expect(barres).toHaveLength(12);
    barres.forEach((barre, i) => expect(barre.getAttribute("style")).toContain(`--i: ${i}`));
  });

  it("dates an older outing", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={{ end_date: "2026-09-06", events: 1, athletes: 5, podiums: 0, courses: [] }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByText("Dernière sortie · 6 sept.")).toBeInTheDocument();
  });

  it("falls back when the season has no outing yet, season figures stay", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByText("Pas encore d'épreuve cette saison")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText("27")).toBeInTheDocument();
  });

  it("says the selection has no outing when it is not exactly the current season", () => {
    const { rerender } = render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2025]} today={TODAY} />);
    expect(screen.getByText("Aucune épreuve pour la saison 2025 — 2026")).toBeInTheDocument();
    rerender(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2025, 2026]} today={TODAY} />);
    expect(screen.getByText("Aucune épreuve pour les 2 saisons sélectionnées")).toBeInTheDocument();
  });

  it("summarises the monthly chart for screen readers", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByRole("img", { name: /Résultats par mois.*sept\. : 120.*oct\. : 192/ })).toBeInTheDocument();
  });

  it("names the selection in the title", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2025, 2026]} today={TODAY} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("2 saisons sélectionnées");
  });

  it("labels the twelve months under the bars and titles each bar with its value", () => {
    const { container } = render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    for (const libelle of ["sept.", "oct.", "nov.", "déc.", "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août"]) {
      expect(screen.getByText(libelle).closest("[aria-hidden='true']")).not.toBeNull();
    }
    const bars = container.querySelectorAll(".tcn-barre");
    expect(bars[0]).toHaveAttribute("title", "sept. : 120");
    expect(bars[1]).toHaveAttribute("title", "oct. : 192");
  });

  it("draws one bar per season and month with a legend when several seasons are selected", () => {
    const stats = { ...STATS, by_month: { ...STATS.by_month, "2025-09": 7 } };
    const { container } = render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={stats} seasons={[2025, 2026]} today={TODAY} />);
    expect(container.querySelectorAll(".tcn-barre")).toHaveLength(24);
    expect(screen.getByText("Saison 2025 — 2026")).toBeInTheDocument();
    expect(screen.getByText("Saison 2026 — 2027")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Saison 2025 — 2026 : sept\. : 7.*Saison 2026 — 2027 : sept\. : 120/ })).toBeInTheDocument();
    expect(screen.queryByText(/saisons les plus récentes/)).toBeNull();
    expect(container.querySelectorAll(".tcn-barre")[0]).toHaveAttribute("title", "Saison 2025 — 2026 · sept. : 7");
  });

  it("notes that only the 3 most recent seasons are drawn", () => {
    const { container } = render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2022, 2023, 2024, 2025]} today={TODAY} />);
    expect(screen.getByText("Seules les 3 saisons les plus récentes sont comparées.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Seules les 3 saisons les plus récentes sont comparées\.$/ })).toBeInTheDocument();
    expect(container.querySelectorAll(".tcn-barre")).toHaveLength(36);
  });

  it("says \"Aucun résultat\" for a closed season without results in compare mode", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2019, 2026]} today={TODAY} />);
    expect(screen.getByRole("img", { name: /Saison 2019 — 2020 : Aucun résultat/ })).toBeInTheDocument();
  });

  it("dates a past season's outing", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={{ end_date: "2026-05-10", events: 1, athletes: 5, podiums: 0, courses: [] }} stats={STATS} seasons={[2025]} today={TODAY} />);
    expect(screen.getByText("Dernière sortie · 10 mai 2026")).toBeInTheDocument();
  });

  it("heads the outing with an h2 so heading navigation reaches it", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={{ end_date: "2026-10-11", events: 3, athletes: 48, podiums: 9, courses: [] }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByRole("heading", { level: 2, name: "Ce week-end" })).toBeInTheDocument();
  });

  it("splits the banner into an outing card and a season card", () => {
    render(<BandeauDirect resultatsHref="/resultats" sortie={{ end_date: "2026-10-11", events: 3, athletes: 48, podiums: 9, courses: [] }} stats={STATS} seasons={[2026]} today={TODAY} />);
    const outing = screen.getByRole("region", { name: "Dernière sortie" });
    expect(within(outing).getByText("Ce week-end")).toBeInTheDocument();
    expect(within(outing).getByText("48 TCN")).toBeInTheDocument();
    expect(outing).toHaveClass("tcn-carte-sortie");
    expect(outing.querySelector(".tcn-carte-sortie-contenu")).toContainElement(within(outing).getByText("Ce week-end"));
    const season = screen.getByRole("region", { name: /Triathlon Club/ });
    expect(within(season).getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(within(season).getByText("312")).toBeInTheDocument();
    expect(within(season).getByText("87")).toBeInTheDocument();
    expect(within(season).getByText("27")).toBeInTheDocument();
    expect(within(season).getByRole("img", { name: /Résultats par mois/ })).toBeInTheDocument();
    expect(within(outing).queryByRole("img")).toBeNull();
  });

  it("keeps the fallback in the outing card and draws bars in orange on the white card", () => {
    const { container } = render(<BandeauDirect resultatsHref="/resultats" sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    const outing = screen.getByRole("region", { name: "Dernière sortie" });
    expect(within(outing).getByText("Pas encore d'épreuve cette saison")).toBeInTheDocument();
    const bars = container.querySelectorAll<HTMLElement>(".tcn-barre");
    expect(bars).toHaveLength(12);
    expect([...bars].some((bar) => bar.style.background === "var(--tcn-orange)")).toBe(true);
  });

  describe("races of the outing", () => {
    const course = (id: number, name: string, tcn: number, podiums: number, event_type = "M") => ({ id, name, event_type, tcn, podiums });
    const trois = [course(1, "Triathlon de Nantes", 36, 5), course(2, "Duathlon de Rezé", 7, 2, "S"), course(3, "Aquathlon de Vertou", 5, 1, "XS")];
    const sortie = (courses: ReturnType<typeof course>[]) => ({ end_date: "2026-10-11", events: courses.length, athletes: 48, podiums: 9, courses });
    const outing = () => screen.getByRole("region", { name: "Dernière sortie" });

    it("lists each race as a link to its page with format, name, TCN count and podiums", () => {
      render(<BandeauDirect resultatsHref="/resultats" sortie={sortie(trois)} stats={STATS} seasons={[2026]} today={TODAY} />);
      const lien = within(outing()).getByRole("link", { name: /Triathlon de Nantes/ });
      expect(lien).toHaveAttribute("href", "/courses/1");
      expect(within(lien).getByText("M")).toBeInTheDocument();
      expect(within(lien).getByText("36")).toBeInTheDocument();
      expect(within(lien).getByText("5 podiums")).toHaveClass("sr-only");
      expect(within(outing()).getAllByRole("link").slice(0, 3).map((a) => a.getAttribute("href"))).toEqual(["/courses/1", "/courses/2", "/courses/3"]);
      expect(outing().querySelector(".tcn-carte-sortie-contenu")).toContainElement(lien);
    });

    it("declares a shrinkable grid column so long names truncate instead of widening the rows", () => {
      render(<BandeauDirect resultatsHref="/resultats" sortie={sortie(trois)} stats={STATS} seasons={[2026]} today={TODAY} />);
      const liste = within(outing()).getByRole("list");
      expect(liste?.style.gridTemplateColumns).toBe("minmax(0, 1fr)");
    });

    it("gives the TCN count an accessible name and hides the bare number", () => {
      render(<BandeauDirect resultatsHref="/resultats" sortie={sortie(trois)} stats={STATS} seasons={[2026]} today={TODAY} />);
      const lien = within(outing()).getByRole("link", { name: /Triathlon de Nantes/ });
      expect(within(lien).getByText("36 athlètes du club")).toHaveClass("sr-only");
      expect(within(lien).getByText("36")).toHaveAttribute("aria-hidden", "true");
      expect(within(lien).getByText("36").parentElement?.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    });

    it("keeps a compact medal and podium count visible on mobile and shows two rows there", () => {
      render(<BandeauDirect resultatsHref="/resultats" sortie={sortie(trois)} stats={STATS} seasons={[2026]} today={TODAY} />);
      const [premiere, , troisieme] = within(outing()).getAllByRole("link");
      const podiums = premiere.querySelector("[data-podiums]");
      expect(podiums).toHaveClass("inline-flex");
      expect(podiums).not.toHaveClass("hidden");
      expect(within(podiums as HTMLElement).getByText("5")).toBeInTheDocument();
      expect(troisieme).toHaveClass("hidden", "md:flex");
      expect(premiere).not.toHaveClass("hidden");
    });

    it("links the remaining races to the results page with the page query", () => {
      const cinq = [...trois, course(4, "D", 3, 0), course(5, "E", 2, 0)];
      render(<BandeauDirect resultatsHref="/resultats?seasons=2026&sports=federal" sortie={sortie(cinq)} stats={STATS} seasons={[2026]} today={TODAY} />);
      expect(within(outing()).getAllByRole("link")).toHaveLength(4);
      expect(within(outing()).getByRole("link", { name: /et 2 autres épreuves/ })).toHaveAttribute("href", "/resultats?seasons=2026&sports=federal");
    });

    it("shows the « autres » link on mobile only when three races fit on desktop, and nowhere for two", () => {
      const { rerender } = render(<BandeauDirect resultatsHref="/resultats" sortie={sortie(trois)} stats={STATS} seasons={[2026]} today={TODAY} />);
      expect(within(outing()).getByRole("link", { name: /et 1 autre épreuve/ })).toHaveClass("md:hidden");
      rerender(<BandeauDirect resultatsHref="/resultats" sortie={sortie(trois.slice(0, 2))} stats={STATS} seasons={[2026]} today={TODAY} />);
      expect(within(outing()).queryByText(/autres? épreuves?/)).toBeNull();
    });
  });
});
