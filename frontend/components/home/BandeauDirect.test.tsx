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
    render(<BandeauDirect sortie={{ end_date: "2026-10-11", events: 3, athletes: 48, podiums: 9 }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByText("Ce week-end")).toBeInTheDocument();
    expect(screen.getByText("48 TCN")).toBeInTheDocument();
    expect(screen.getByText(/3 épreuves · 9 podiums/)).toBeInTheDocument();
  });

  it("pulses next to « Ce week-end » only for a very recent outing", () => {
    const { container, rerender } = render(<BandeauDirect sortie={{ end_date: "2026-10-14", events: 1, athletes: 5, podiums: 0 }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(container.querySelector(".tcn-pouls")).toHaveAttribute("aria-hidden", "true");
    rerender(<BandeauDirect sortie={{ end_date: "2026-10-10", events: 1, athletes: 5, podiums: 0 }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(container.querySelector(".tcn-pouls")).toBeNull();
  });

  it("indexes each histogram bar for the staggered growth", () => {
    const { container } = render(<BandeauDirect sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    const barres = [...container.querySelectorAll(".tcn-barre")];
    expect(barres).toHaveLength(12);
    barres.forEach((barre, i) => expect(barre.getAttribute("style")).toContain(`--i: ${i}`));
  });

  it("dates an older outing", () => {
    render(<BandeauDirect sortie={{ end_date: "2026-09-06", events: 1, athletes: 5, podiums: 0 }} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByText("Dernière sortie · 6 sept.")).toBeInTheDocument();
  });

  it("falls back when the season has no outing yet, season figures stay", () => {
    render(<BandeauDirect sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByText("Pas encore d'épreuve cette saison")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText("27")).toBeInTheDocument();
  });

  it("summarises the monthly chart for screen readers", () => {
    render(<BandeauDirect sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    expect(screen.getByRole("img", { name: /Résultats par mois.*sept\. : 120.*oct\. : 192/ })).toBeInTheDocument();
  });

  it("names the selection in the title and the latest season on the chart", () => {
    render(<BandeauDirect sortie={null} stats={STATS} seasons={[2025, 2026]} today={TODAY} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("2 saisons sélectionnées");
    expect(screen.getByText("Résultats par mois · Saison 2026 — 2027")).toBeInTheDocument();
  });

  it("dates a past season's outing", () => {
    render(<BandeauDirect sortie={{ end_date: "2026-05-10", events: 1, athletes: 5, podiums: 0 }} stats={STATS} seasons={[2025]} today={TODAY} />);
    expect(screen.getByText("Dernière sortie · 10 mai")).toBeInTheDocument();
  });

  it("splits the banner into an outing card and a season card", () => {
    render(<BandeauDirect sortie={{ end_date: "2026-10-11", events: 3, athletes: 48, podiums: 9 }} stats={STATS} seasons={[2026]} today={TODAY} />);
    const outing = screen.getByRole("region", { name: "Dernière sortie" });
    expect(within(outing).getByText("Ce week-end")).toBeInTheDocument();
    expect(within(outing).getByText("48 TCN")).toBeInTheDocument();
    expect(outing).toHaveClass("tcn-carte-sortie");
    const season = screen.getByRole("region", { name: /Triathlon Club/ });
    expect(within(season).getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(within(season).getByText("312")).toBeInTheDocument();
    expect(within(season).getByText("87")).toBeInTheDocument();
    expect(within(season).getByText("27")).toBeInTheDocument();
    expect(within(season).getByRole("img", { name: /Résultats par mois/ })).toBeInTheDocument();
    expect(within(outing).queryByRole("img")).toBeNull();
  });

  it("keeps the fallback in the outing card and draws bars in orange on the white card", () => {
    const { container } = render(<BandeauDirect sortie={null} stats={STATS} seasons={[2026]} today={TODAY} />);
    const outing = screen.getByRole("region", { name: "Dernière sortie" });
    expect(within(outing).getByText("Pas encore d'épreuve cette saison")).toBeInTheDocument();
    const bars = container.querySelectorAll<HTMLElement>(".tcn-barre");
    expect(bars).toHaveLength(12);
    expect([...bars].some((bar) => bar.style.background === "var(--tcn-orange)")).toBe(true);
  });
});
