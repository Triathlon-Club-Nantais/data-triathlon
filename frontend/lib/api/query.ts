/**
 * Construction de query string, partagée par `client.ts` (fetch navigateur) et
 * `server.ts` (fetch RSC).
 *
 * Les deux en portaient une copie strictement identique. C'est la **seule**
 * chose à mutualiser entre eux : `serverFetch` et `serverFetchAuthed` restent
 * deux fonctions distinctes (lire les cookies dans la première rendrait
 * dynamiques les six pages publiques prérendues), et `client.ts` vise `/api/v1`
 * en relatif là où `server.ts` vise `API_URL`.
 */
export function toQuery(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (Array.isArray(v)) {
      if (v.length > 0) params.set(k, v.join(","));
      return;
    }
    params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

/** Le `detail` d'une réponse non-OK, ou son `statusText` à défaut de corps JSON. */
export async function detailDErreur(res: Response): Promise<string> {
  const corps = await res.json().catch(() => ({ detail: res.statusText }));
  return corps.detail || `Erreur API (${res.status})`;
}
