import { describe, it, expect, vi, afterEach } from "vitest";
import { apiServer } from "@/lib/api/server";

afterEach(() => {
  vi.unstubAllGlobals();
});

function mockFetchOk(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("serverFetch — fenêtre de revalidation (#352)", () => {
  it("garde `no-store` par défaut, sans option de revalidation", async () => {
    const fetchMock = mockFetchOk({ total: 0, athletes: 0, events: 0, by_type: {}, by_month: {}, recent: [] });

    await apiServer.getStats({ scope: "club" });

    const [, options] = fetchMock.mock.calls[0];
    expect(options).toEqual({ cache: "no-store" });
  });

  it("bascule sur `next.revalidate` quand une fenêtre est demandée", async () => {
    const fetchMock = mockFetchOk({ total: 0, athletes: 0, events: 0, by_type: {}, by_month: {}, recent: [] });

    await apiServer.getStats({ scope: "club" }, { revalidateSeconds: 30 });

    const [, options] = fetchMock.mock.calls[0];
    expect(options).toEqual({ next: { revalidate: 30 } });
  });

  it("propage la fenêtre de revalidation sur listParticipations, listEvents et listSeasons", async () => {
    const fetchMockParticipations = mockFetchOk([]);
    await apiServer.listParticipations({ scope: "club" }, { revalidateSeconds: 30 });
    expect(fetchMockParticipations.mock.calls[0][1]).toEqual({ next: { revalidate: 30 } });

    const fetchMockEvents = mockFetchOk({ items: [], total_events: 0, total_participations: 0 });
    await apiServer.listEvents({ scope: "club" }, { revalidateSeconds: 30 });
    expect(fetchMockEvents.mock.calls[0][1]).toEqual({ next: { revalidate: 30 } });

    const fetchMockSeasons = mockFetchOk([]);
    await apiServer.listSeasons({ scope: "club" }, { revalidateSeconds: 30 });
    expect(fetchMockSeasons.mock.calls[0][1]).toEqual({ next: { revalidate: 30 } });
  });
});
