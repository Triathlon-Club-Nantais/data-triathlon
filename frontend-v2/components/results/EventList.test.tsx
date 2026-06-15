import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const eventsMock = vi.hoisted(() => ({
  value: {} as ReturnType<typeof Object>,
}));

vi.mock("@/lib/queries/events", () => ({
  EVENTS_PAGE_SIZE: 30,
  useInfiniteEvents: () => eventsMock.value,
  useCourseParticipations: () => ({ data: [], isLoading: false, isError: false }),
}));
vi.mock("@/lib/queries/participations", () => ({
  useDeleteParticipation: () => ({ mutateAsync: vi.fn() }),
}));

import { EventList } from "./EventList";

function setEvents(value: unknown) {
  eventsMock.value = value as never;
}

function renderList(filters = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <EventList filters={filters} />
    </QueryClientProvider>,
  );
}

describe("EventList", () => {
  it("affiche les épreuves avec libellé de discipline et compteurs", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 1,
                event_name: "Tri de Nantes",
                event_type: "triathlon-m",
                event_date: "2026-05-16",
                is_relay: false,
                total: 42,
                tcn_count: 3,
              },
            ],
            total_events: 1,
            total_participations: 42,
          },
        ],
      },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();

    expect(screen.getByText("Tri de Nantes")).toBeInTheDocument();
    expect(screen.getByText("Triathlon M")).toBeInTheDocument();
    expect(screen.getByText("42 résultats")).toBeInTheDocument();
    expect(screen.getByText("3 TCN")).toBeInTheDocument();
  });

  it("affiche un état vide quand aucune épreuve", () => {
    setEvents({
      data: { pages: [{ items: [], total_events: 0, total_participations: 0 }] },
      fetchNextPage: vi.fn(),
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
    });

    renderList();
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
  });
});
