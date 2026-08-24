import { describe, it, expect, vi, afterEach } from "vitest";
import { apiServer } from "@/lib/api/server";
import { NAV_WIDTH_COOKIE } from "@/lib/nav-cookies";

const { getAll } = vi.hoisted(() => ({
  getAll: vi.fn(() => [{ name: "tcn_site_session", value: "jeton-de-test" }]),
}));

vi.mock("next/headers", () => ({
  cookies: async () => ({ getAll }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  getAll.mockReturnValue([{ name: "tcn_site_session", value: "jeton-de-test" }]);
});

function mockFetchOk(body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("serverFetch — relais du cookie d'accès au site (#526)", () => {
  it("relaie les cookies entrants : les routes de lecture sont derrière le mot de passe site", async () => {
    const fetchMock = mockFetchOk({
      total: 0,
      athletes: 0,
      events: 0,
      by_type: {},
      by_month: {},
      recent: [],
    });

    await apiServer.getStats({ scope: "club" });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toEqual({ cookie: "tcn_site_session=jeton-de-test" });
  });

  it("relaie aussi le cookie quand une fenêtre de revalidation est demandée", async () => {
    const fetchMock = mockFetchOk([]);

    await apiServer.listParticipations({ scope: "club" }, { revalidateSeconds: 30 });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toEqual({ cookie: "tcn_site_session=jeton-de-test" });
  });

  it("exclut le cookie de largeur du rail — une préférence d'affichage, jamais lue par l'API (#482, NAV-3)", async () => {
    getAll.mockReturnValue([
      { name: "tcn_site_session", value: "jeton-de-test" },
      { name: NAV_WIDTH_COOKIE, value: "1" },
    ]);
    const fetchMock = mockFetchOk({ total: 0, athletes: 0, events: 0, by_type: {}, by_month: {}, recent: [] });

    await apiServer.getStats({ scope: "club" });

    // Sans quoi la clé du Data Cache (#526) varierait avec un cookie que
    // l'API n'utilise pas, cassant le partage inter-visiteurs de la fenêtre
    // de revalidation de #352 sur `/dashboard`, `/club` et `/ajouter`.
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toEqual({ cookie: "tcn_site_session=jeton-de-test" });
  });
});

describe("serverFetch — fenêtre de revalidation (#352)", () => {
  it("garde `no-store` par défaut, sans option de revalidation", async () => {
    const fetchMock = mockFetchOk({ total: 0, athletes: 0, events: 0, by_type: {}, by_month: {}, recent: [] });

    await apiServer.getStats({ scope: "club" });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.cache).toBe("no-store");
    expect(options.next).toBeUndefined();
  });

  it("bascule sur `next.revalidate` quand une fenêtre est demandée", async () => {
    const fetchMock = mockFetchOk({ total: 0, athletes: 0, events: 0, by_type: {}, by_month: {}, recent: [] });

    await apiServer.getStats({ scope: "club" }, { revalidateSeconds: 30 });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.next).toEqual({ revalidate: 30 });
    // Exclusif : `no-store` gagnerait sur `next.revalidate` et annulerait la fenêtre.
    expect(options.cache).toBeUndefined();
  });

  it("propage la fenêtre de revalidation sur listParticipations, listEvents et listSeasons", async () => {
    const fetchMockParticipations = mockFetchOk([]);
    await apiServer.listParticipations({ scope: "club" }, { revalidateSeconds: 30 });
    expect(fetchMockParticipations.mock.calls[0][1].next).toEqual({ revalidate: 30 });

    const fetchMockEvents = mockFetchOk({ items: [], total_events: 0, total_participations: 0 });
    await apiServer.listEvents({ scope: "club" }, { revalidateSeconds: 30 });
    expect(fetchMockEvents.mock.calls[0][1].next).toEqual({ revalidate: 30 });

    const fetchMockSeasons = mockFetchOk([]);
    await apiServer.listSeasons({ scope: "club" }, { revalidateSeconds: 30 });
    expect(fetchMockSeasons.mock.calls[0][1].next).toEqual({ revalidate: 30 });
  });
});
