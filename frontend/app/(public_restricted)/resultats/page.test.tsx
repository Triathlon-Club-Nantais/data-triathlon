import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";

const listEvents = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    listEvents: (filters: unknown, fetchOpts?: unknown) => listEvents(filters, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/resultats",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/layout/ScopeToggle", () => ({
  ScopeToggle: () => <div data-testid="scope-toggle-stub" />,
}));

vi.mock("@/components/results/ResultsFilters", () => ({
  ResultsFilters: () => <div data-testid="results-filters-stub" />,
}));

vi.mock("@/components/results/EventList", () => ({
  EventList: () => <div data-testid="event-list-stub" />,
}));

import ResultatsPage from "./page";

const FIRST_PAGE = {
  items: [],
  total_events: 3,
  total_participations: 7,
  page: 1,
  page_size: 20,
  total_pages: 1,
};

describe("ResultatsPage", () => {
  it("récupère la page 1 avec la fenêtre de revalidation courte (#623)", async () => {
    listEvents.mockResolvedValue(FIRST_PAGE);

    const jsx = await ResultatsPage({ searchParams: Promise.resolve({}) });
    render(jsx);

    expect(listEvents).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  it("un ?sort= inconnu dans l'URL ne remonte pas tel quel à l'API (#711)", async () => {
    listEvents.mockResolvedValue(FIRST_PAGE);

    const jsx = await ResultatsPage({ searchParams: Promise.resolve({ sort: "banana" }) });
    render(jsx);

    const [filters] = listEvents.mock.calls[0] as [{ sort?: string }];
    expect(filters.sort).toBeUndefined();
  });
});
