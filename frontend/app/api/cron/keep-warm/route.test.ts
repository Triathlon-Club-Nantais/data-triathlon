import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { GET } from "./route";

beforeEach(() => {
  // Silence les console.error attendus (cas 502) pour ne pas polluer la sortie des tests.
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function makeRequest(headers: Record<string, string> = {}): Request {
  return new Request("http://localhost/api/cron/keep-warm", { headers });
}

describe("GET /api/cron/keep-warm", () => {
  it("répond 401 si CRON_SECRET est défini et l'en-tête Authorization manque", async () => {
    vi.stubEnv("CRON_SECRET", "s3cr3t");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET(makeRequest());

    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
    await expect(res.json()).resolves.toMatchObject({ ok: false });
  });

  it("répond 200 et ping /api/v1/health quand le secret est correct", async () => {
    vi.stubEnv("CRON_SECRET", "s3cr3t");
    vi.stubEnv("BACKEND_URL", "https://backend.test");
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET(makeRequest({ authorization: "Bearer s3cr3t" }));

    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toMatchObject({ ok: true, backendStatus: 200 });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.test/api/v1/health",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("répond 502 quand le backend renvoie un statut non-2xx", async () => {
    vi.stubEnv("CRON_SECRET", "s3cr3t");
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET(makeRequest({ authorization: "Bearer s3cr3t" }));

    expect(res.status).toBe(502);
    await expect(res.json()).resolves.toMatchObject({ ok: false });
  });

  it("répond 502 quand fetch rejette (réseau / timeout)", async () => {
    vi.stubEnv("CRON_SECRET", "s3cr3t");
    const fetchMock = vi.fn().mockRejectedValue(new Error("network down"));
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET(makeRequest({ authorization: "Bearer s3cr3t" }));

    expect(res.status).toBe(502);
    await expect(res.json()).resolves.toMatchObject({ ok: false, error: "network down" });
  });

  it("ignore l'auth en dev quand CRON_SECRET est absent", async () => {
    vi.stubEnv("CRON_SECRET", "");
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET(makeRequest());

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalled();
  });

  it("répond 401 quand l'en-tête Authorization est présent mais incorrect", async () => {
    vi.stubEnv("CRON_SECRET", "s3cr3t");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET(makeRequest({ authorization: "Bearer mauvais" }));

    expect(res.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("répond 502 avec un message français quand le fetch expire (AbortError)", async () => {
    vi.stubEnv("CRON_SECRET", "s3cr3t");
    const abortErr = Object.assign(new Error("This operation was aborted"), {
      name: "AbortError",
    });
    const fetchMock = vi.fn().mockRejectedValue(abortErr);
    vi.stubGlobal("fetch", fetchMock);

    const res = await GET(makeRequest({ authorization: "Bearer s3cr3t" }));

    expect(res.status).toBe(502);
    await expect(res.json()).resolves.toMatchObject({ ok: false, error: "délai dépassé" });
  });
});
