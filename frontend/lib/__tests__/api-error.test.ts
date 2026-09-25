import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "@/lib/api/client";

/**
 * Une réponse non-OK levait un `Error` nu : un 401 y était indiscernable d'un
 * 500. La session en dépend — « pas connecté » est un état normal de la page,
 * pas une panne à signaler.
 */
describe("ApiError", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function repond(status: number, body: unknown, headers: Record<string, string> = {}) {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: status < 400,
      status,
      statusText: "",
      headers: new Headers(headers),
      json: async () => body,
    });
  }

  it("porte le statut HTTP de la réponse", async () => {
    repond(401, { detail: "Vous devez être connecté." });

    await expect(apiClient.getSession()).rejects.toSatisfy(
      (erreur: unknown) => erreur instanceof ApiError && erreur.status === 401,
    );
  });

  it("aplatit le `detail` liste d'une validation Pydantic", async () => {
    // Sans quoi `new Error(detail)` affichait « [object Object] » dans un toast.
    repond(422, {
      detail: [{ loc: ["body", "email"], msg: "adresse invalide", type: "value_error" }],
    });

    const erreur = await apiClient.getSession().catch((e) => e);
    expect(erreur.message).toBe("adresse invalide");
  });

  it("retombe sur un message lisible quand `detail` est inexploitable", async () => {
    repond(500, { detail: [] });

    const erreur = await apiClient.getSession().catch((e) => e);
    expect(erreur.message).not.toContain("object Object");
  });

  it("distingue un 401 d'un 500", async () => {
    repond(500, { detail: "Boum" });

    const erreur = await apiClient.getSession().catch((e) => e);
    expect(erreur).toBeInstanceOf(ApiError);
    expect(erreur.status).toBe(500);
  });

  it("conserve le message français rendu par l'API", async () => {
    repond(422, { detail: "URL invalide" });

    const erreur = await apiClient.detectProvider("x").catch((e) => e);
    expect(erreur.message).toBe("URL invalide");
  });

  it("reste une Error, pour ne rien casser de l'existant", async () => {
    repond(404, { detail: "Ressource introuvable" });

    const erreur = await apiClient.getCourse(1).catch((e) => e);
    expect(erreur).toBeInstanceOf(Error);
  });

  it("carries the Retry-After wait of a 429", async () => {
    repond(429, { detail: "Trop de requêtes" }, { "Retry-After": "12" });

    const erreur = await apiClient.getSession().catch((e) => e);
    expect(erreur.status).toBe(429);
    expect(erreur.retryAfter).toBe(12);
  });

  it("leaves retryAfter null when the header is missing or unreadable", async () => {
    repond(429, { detail: "Trop de requêtes" }, { "Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT" });
    expect((await apiClient.getSession().catch((e) => e)).retryAfter).toBeNull();

    repond(429, { detail: "Trop de requêtes" });
    expect((await apiClient.getSession().catch((e) => e)).retryAfter).toBeNull();
  });

  it("carries the Retry-After wait of a 429 on a multipart upload", async () => {
    repond(429, { detail: "Trop de requêtes" }, { "Retry-After": "30" });

    const erreur = await apiClient.readSheetColumns(new File(["a"], "a.csv")).catch((e) => e);
    expect(erreur.status).toBe(429);
    expect(erreur.retryAfter).toBe(30);
  });
});
