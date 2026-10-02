import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request() error messages (#1045)", () => {
  it("keeps the machine-readable code of a refusal (#877)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Code d'accès au site requis.", code: "site_access_required" }),
          { status: 401 },
        ),
      ),
    );

    const erreur = (await apiClient.listProviders().catch((e: unknown) => e)) as ApiError;

    expect(erreur.status).toBe(401);
    expect(erreur.code).toBe("site_access_required");
  });

  it("keeps the additive fields of a refusal body, such as the conflicting record (#908)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Un athlète porte déjà cette identité (fiche n° 77).", conflicting_athlete_id: 77 }),
          { status: 409 },
        ),
      ),
    );

    const erreur = (await apiClient.updateAthlete(42, { nom: "X" }).catch((e: unknown) => e)) as ApiError;

    expect(erreur.status).toBe(409);
    expect(erreur.details.conflicting_athlete_id).toBe(77);
  });

  it("leaves the code null when the server sends none", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Non connecté" }), { status: 401 })),
    );

    const erreur = (await apiClient.listProviders().catch((e: unknown) => e)) as ApiError;

    expect(erreur.code).toBeNull();
  });

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

  // #1019 : `POST /participations` refuse en 422 champ par champ ; le formulaire
  // manuel en tire un message sous chaque champ.
  it("sorts a 422 validation detail by field, keeping the type and the server message", async () => {
    const detail = [
      { type: "string_pattern_mismatch", loc: ["body", "swim_time"], msg: "String should match pattern '^…$'" },
      { type: "value_error", loc: ["body", "event_type"], msg: "Value error, Type d'épreuve inconnu." },
      { type: "date_from_datetime_parsing", loc: ["body", "event_date"], msg: "Input should be a valid date" },
      { type: "string_too_short", loc: ["body", "athlete_name"], msg: "String should have at least 1 character" },
      { type: "greater_than_equal", loc: ["body", "rank_overall"], msg: "Input should be greater than or equal to 1" },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 422 })),
    );

    const erreur = (await apiClient.saveParticipation({}).catch((e: unknown) => e)) as ApiError;

    expect(erreur).toBeInstanceOf(ApiError);
    expect(erreur.status).toBe(422);
    expect(erreur.fieldErrors).toEqual({
      swim_time: { type: "string_pattern_mismatch", message: "String should match pattern '^…$'" },
      event_type: { type: "value_error", message: "Type d'épreuve inconnu." },
      event_date: { type: "date_from_datetime_parsing", message: "Input should be a valid date" },
      athlete_name: { type: "string_too_short", message: "String should have at least 1 character" },
      rank_overall: { type: "greater_than_equal", message: "Input should be greater than or equal to 1" },
    });
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
