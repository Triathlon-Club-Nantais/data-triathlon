import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SeasonQuota } from "@/lib/types";

const { getMySeasonQuota } = vi.hoisted(() => ({ getMySeasonQuota: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getMySeasonQuota } };
});

import { seasonLabel } from "@/lib/utils/season";
import { MaSaisonAuClub } from "./MaSaisonAuClub";

const quota = (extra: Partial<SeasonQuota> = {}): SeasonQuota => ({
  validated_count: 0, has_volunteer_action: false, has_pending_volunteer_action: false,
  season_validated: false, quota_met: false, season: 2026, required_events: 3, ...extra,
});

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MaSaisonAuClub /></QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe("MaSaisonAuClub", () => {
  it("shows validated season", async () => {
    getMySeasonQuota.mockResolvedValue(quota({ season_validated: true, quota_met: true }));
    afficher();
    expect(await screen.findByText("Saison validée")).toBeInTheDocument();
  });

  it("shows quota met awaiting club validation", async () => {
    getMySeasonQuota.mockResolvedValue(quota({ quota_met: true }));
    afficher();
    expect(await screen.findByText("Conditions remplies, en attente de validation par le club")).toBeInTheDocument();
  });

  it("shows what is missing", async () => {
    getMySeasonQuota.mockResolvedValue(quota({ validated_count: 1, has_pending_volunteer_action: true }));
    afficher();
    expect(await screen.findByText(/1 épreuve comptée/)).toBeInTheDocument();
    expect(screen.getByText(/3 requises/)).toBeInTheDocument();
    expect(screen.getByText(/en attente de validation/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Déclarer une action/ })).toBeNull();
  });

  it("links to volunteering when no action was declared", async () => {
    getMySeasonQuota.mockResolvedValue(quota({ validated_count: 3 }));
    afficher();
    expect(await screen.findByRole("link", { name: /Déclarer une action/ })).toHaveAttribute("href", "/benevolat");
  });

  it("pluralises counted events", async () => {
    getMySeasonQuota.mockResolvedValue(quota({ validated_count: 2, has_volunteer_action: true }));
    afficher();
    expect(await screen.findByText(/2 épreuves comptées/)).toBeInTheDocument();
  });

  it("does not show more events than required", async () => {
    getMySeasonQuota.mockResolvedValue(quota({ validated_count: 5 }));
    afficher();
    expect(await screen.findByText(/objectif de 3 atteint/)).toBeInTheDocument();
    expect(screen.queryByText(/5 épreuves comptées sur 3/)).toBeNull();
    expect(screen.getByText(/aucune action déclarée/)).toBeInTheDocument();
  });

  it("shows a short message on network error", async () => {
    getMySeasonQuota.mockRejectedValue(new Error("boom"));
    afficher();
    expect(await screen.findByText(/Impossible d.afficher votre saison/)).toBeInTheDocument();
  });

  it("renders nothing when the API returns null", async () => {
    getMySeasonQuota.mockResolvedValue(null);
    const { container } = afficher();
    await vi.waitFor(() => expect(getMySeasonQuota).toHaveBeenCalled());
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("shows the season in the title", async () => {
    getMySeasonQuota.mockResolvedValue(quota({ season: 2026 }));
    afficher();
    expect(await screen.findByText(seasonLabel(2026))).toBeInTheDocument();
  });
});
