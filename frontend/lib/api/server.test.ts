import { describe, it, expect, vi, afterEach } from "vitest";
import { apiServer } from "@/lib/api/server";
import { NAV_WIDTH_COOKIE } from "@/lib/nav-cookies";

const DEFAULT_COOKIES = [{ name: "tcn_site_session", value: "jeton-de-test" }];

const { getAll } = vi.hoisted(() => ({
  getAll: vi.fn(() => [{ name: "tcn_site_session", value: "jeton-de-test" }]),
}));

vi.mock("next/headers", () => ({
  // `get` doit refléter `getAll` : `serverFetch` (#586) ne lit plus le jar que
  // par `get(SITE_SESSION_COOKIE)`, un mock qui ne porterait que `getAll`
  // laisserait passer une régression sans qu'aucun test ne le voie planter.
  cookies: async () => ({
    getAll,
    get: (name: string) => getAll().find((c) => c.name === name),
  }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  getAll.mockReturnValue(DEFAULT_COOKIES);
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

  it("n'envoie que le cookie d'accès au site — pas la session SSO, ni un cookie bénévoles ou PostHog (#586)", async () => {
    getAll.mockReturnValue([
      { name: "tcn_site_session", value: "jeton-de-test" },
      { name: "tcn_session", value: "session-sso" },
      { name: "tcn_logged_in", value: "1" },
      { name: "tcn_benevole_session", value: "session-benevoles" },
      { name: "ph_phc_test", value: "device-id" },
      { name: NAV_WIDTH_COOKIE, value: "1" },
    ]);
    const fetchMock = mockFetchOk([]);

    await apiServer.listParticipations({ scope: "club" }, { revalidateSeconds: 30 });

    // Avant #586, `serverFetch` relayait le jar entier (hors NAV_WIDTH_COOKIE) :
    // un cookie que `require_site_access` ne lit jamais faisait quand même
    // varier la clé du Data Cache, jusqu'à casser le partage *intra-visiteur*
    // qu'un simple rechargement de page devrait garder — un cookie PostHog qui
    // tourne, ou `tcn_session` posé/retiré par une connexion SSO, suffisait.
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toEqual({ cookie: "tcn_site_session=jeton-de-test" });
  });

  it("n'envoie aucun cookie si le visiteur n'a pas encore ouvert de session d'accès au site", async () => {
    getAll.mockReturnValue([{ name: "tcn_session", value: "session-sso" }]);
    const fetchMock = mockFetchOk([]);

    await apiServer.listParticipations({ scope: "club" });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toEqual({ cookie: "" });
  });
});

describe("serverFetchAuthed / serverFetchAuthedRaw — relaient le jar entier (#586)", () => {
  it("`getSession` relaie la session SSO — elle n'est jamais mise en cache, aucun coût de clé à réduire", async () => {
    getAll.mockReturnValue([
      { name: "tcn_site_session", value: "jeton-de-test" },
      { name: "tcn_session", value: "session-sso" },
    ]);
    const fetchMock = mockFetchOk({ id: 1, email: "a@b.fr", permissions: [], roles: [], groups: [] });

    await apiServer.getSession();

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toEqual({
      cookie: "tcn_site_session=jeton-de-test; tcn_session=session-sso",
    });
  });

  it("`checkSiteAccess` relaie le jar entier, hors cookie de largeur du rail", async () => {
    getAll.mockReturnValue([
      { name: "tcn_site_session", value: "jeton-de-test" },
      { name: NAV_WIDTH_COOKIE, value: "1" },
    ]);
    const fetchMock = mockFetchOk({ ok: true });

    await apiServer.checkSiteAccess();

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

  it("propage la fenêtre de revalidation sur getClubSummary (#581)", async () => {
    const fetchMock = mockFetchOk({
      rosters: { tcn: [], other: [] },
      podiums: [],
    });

    await apiServer.getClubSummary({ federal_only: true }, { revalidateSeconds: 30 });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/club/summary?federal_only=true");
    expect(options.next).toEqual({ revalidate: 30 });
  });
});
