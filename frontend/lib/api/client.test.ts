import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request() error messages (#1045)", () => {
  it("names a 5xx with a non-JSON body as an unavailable service, not a network error", async () => {
    // HTTP/2 : `statusText` est toujours vide.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 503, statusText: "" })),
    );

    const erreur = await apiClient.listProviders().catch((e: unknown) => e);

    expect(erreur).toBeInstanceOf(ApiError);
    expect((erreur as ApiError).status).toBe(503);
    expect((erreur as ApiError).message).toBe(
      "Le service est momentanément indisponible. Réessayez dans un instant.",
    );
  });

  it("turns a rejected fetch into a French network ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const erreur = await apiClient.listProviders().catch((e: unknown) => e);

    expect(erreur).toBeInstanceOf(ApiError);
    expect((erreur as ApiError).status).toBe(0);
    expect((erreur as ApiError).message).toBe(
      "Erreur réseau : vérifiez votre connexion puis réessayez.",
    );
  });
});
