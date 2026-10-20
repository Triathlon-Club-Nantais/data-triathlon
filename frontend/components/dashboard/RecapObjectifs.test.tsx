import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SeasonGoal } from "@/lib/types";

const { getSeasonGoals } = vi.hoisted(() => ({ getSeasonGoals: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { ...original.apiClient, getSeasonGoals } };
});

import { RecapObjectifs } from "./RecapObjectifs";

const TEMPS: SeasonGoal = {
  id: 1, season: 2024, kind: "time", event_type: "triathlon-m", target: 9000,
  best_time: "2:35:10", count: null, reached: false,
};
const NOMBRE: SeasonGoal = {
  id: 2, season: 2024, kind: "count", event_type: null, target: 6, best_time: null, count: 6, reached: true,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendu = render(
    <QueryClientProvider client={client}>
      <RecapObjectifs season={2024} />
    </QueryClientProvider>,
  );
  return { ...rendu, client };
}

function settled(client: QueryClient) {
  return vi.waitFor(() => expect(client.isFetching()).toBe(0)).then(() =>
    expect(client.getQueryCache().getAll().every((q) => q.state.status !== "pending")).toBe(true),
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getSeasonGoals.mockResolvedValue([TEMPS, NOMBRE]);
});

describe("RecapObjectifs (#1669)", () => {
  it("requests the recap season", async () => {
    afficher();
    await screen.findByText("Mes objectifs");
    expect(getSeasonGoals).toHaveBeenCalledWith(2024);
  });

  it("shows each goal with its final outcome", async () => {
    afficher();
    const temps = (await screen.findByText("Triathlon M en moins de 2:30:00")).closest("li") as HTMLElement;
    expect(temps).toHaveTextContent("Meilleur temps : 2:35:10");
    expect(temps).toHaveTextContent("Non atteint");
    const nombre = screen.getByText("6 épreuves").closest("li") as HTMLElement;
    expect(nombre).toHaveTextContent("6 sur 6");
    expect(nombre).toHaveTextContent("Atteint");
    expect(nombre).not.toHaveTextContent("Non atteint");
  });

  it("renders nothing without goals", async () => {
    getSeasonGoals.mockResolvedValue([]);
    const { container, client } = afficher();
    await settled(client);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when goals fail to load", async () => {
    getSeasonGoals.mockRejectedValue(new Error("boom"));
    const { container, client } = afficher();
    await settled(client);
    expect(container).toBeEmptyDOMElement();
  });

  it("is read only", async () => {
    afficher();
    await screen.findByText("Mes objectifs");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });
});
