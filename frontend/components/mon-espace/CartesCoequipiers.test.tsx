import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { GeoEvent } from "@/lib/types";

const { getMyTeammates, getEventsGeo } = vi.hoisted(() => ({ getMyTeammates: vi.fn(), getEventsGeo: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getMyTeammates, getEventsGeo } };
});

import { MesCoequipiers } from "./MesCoequipiers";
import { MiniCarte } from "./MiniCarte";

function afficher(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe("MesCoequipiers", () => {
  it("lists teammates with a compare link preselecting them", async () => {
    getMyTeammates.mockResolvedValue([{ athlete_id: 7, prenom: "Paul", nom: "Durand", courses_communes: 3 }]);
    afficher(<MesCoequipiers athleteId={42} seasons={[2025]} federalOnly />);

    expect(await screen.findByText("Paul Durand")).toBeInTheDocument();
    expect(screen.getByText("3 épreuves en commun")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Me comparer à Paul Durand/ })).toHaveAttribute("href", "/athletes/42?comparer=7");
    expect(getMyTeammates).toHaveBeenCalledWith({ federal_only: true, seasons: [2025] });
  });

  it("says so when there is no teammate", async () => {
    getMyTeammates.mockResolvedValue([]);
    afficher(<MesCoequipiers athleteId={42} seasons={[]} federalOnly={false} />);

    expect(await screen.findByText(/Aucun coéquipier de course/)).toBeInTheDocument();
  });
});

const geo = (course_id: number, event_name: string, lat: number, lon: number) =>
  ({ course_id, event_name, event_date: "2026-06-01", event_type: "triathlon-m", count: 10, tcn_count: 2, lat, lon }) as GeoEvent;

describe("MiniCarte", () => {
  it("draws only my races and lists their places as text", async () => {
    getEventsGeo.mockResolvedValue([geo(1, "Triathlon de Nantes", 47.2, -1.5), geo(2, "Swimrun de Vannes", 47.6, -2.7), geo(3, "Autre", 43, 5)]);
    afficher(<MiniCarte courseIds={[1, 2]} />);

    const carte = await screen.findByRole("img", { name: /2 épreuves/ });
    expect(carte.querySelectorAll("circle")).toHaveLength(2);
    expect(screen.getByText("Triathlon de Nantes")).toBeInTheDocument();
    expect(screen.getByText("Swimrun de Vannes")).toBeInTheDocument();
    expect(screen.queryByText("Autre")).not.toBeInTheDocument();
  });

  it("renders nothing when none of my races is located", async () => {
    getEventsGeo.mockResolvedValue([geo(3, "Autre", 43, 5)]);
    const { container } = afficher(<MiniCarte courseIds={[1]} />);

    await vi.waitFor(() => expect(getEventsGeo).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
