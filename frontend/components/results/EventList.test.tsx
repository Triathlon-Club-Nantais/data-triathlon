import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const eventsMock = vi.hoisted(() => ({
  value: {} as ReturnType<typeof Object>,
}));

vi.mock("@/lib/queries/events", () => ({
  EVENTS_PAGE_SIZE: 30,
  useInfiniteEvents: () => eventsMock.value,
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
  it("rend chaque épreuve comme un lien vers sa fiche course", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
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

    const link = screen.getByRole("link", { name: /Tri de Nantes/ });
    expect(link).toHaveAttribute("href", "/courses/14");
    // Métadonnées conservées dans la ligne.
    expect(link).toHaveTextContent("Triathlon M");
    expect(link).toHaveTextContent("42 résultats");
    expect(link).toHaveTextContent("3");
  });

  it("n'affiche plus de bouton de suppression ni d'accordéon", () => {
    setEvents({
      data: {
        pages: [
          {
            items: [
              {
                id: 14,
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

    expect(screen.queryByRole("button", { name: /supprimer/i })).toBeNull();
    // L'épreuve est un lien plein, plus un trigger d'accordéon dépliable.
    expect(screen.queryByRole("button", { name: /Tri de Nantes/i })).toBeNull();
    expect(screen.getByRole("link", { name: /Tri de Nantes/ })).toBeInTheDocument();
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
