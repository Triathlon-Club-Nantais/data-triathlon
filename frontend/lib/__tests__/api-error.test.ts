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

  function repond(status: number, body: unknown) {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: status < 400,
      status,
      statusText: "",
      json: async () => body,
    });
  }

  it("porte le statut HTTP de la réponse", async () => {
    repond(401, { detail: "Vous devez être connecté." });

    await expect(apiClient.getSession()).rejects.toSatisfy(
      (erreur: unknown) => erreur instanceof ApiError && erreur.status === 401,
    );
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
});
