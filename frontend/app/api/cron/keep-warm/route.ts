import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";

// Rendu dynamique : le ping doit s'exécuter à chaque appel, jamais mis en cache statiquement.
export const dynamic = "force-dynamic";

const HEALTH_PATH = "/api/v1/health";
const TIMEOUT_MS = 10_000;

// Cron « keep-warm » : maintient le backend Render éveillé (évite le cold start ~15 min).
//
// Appelée toutes les ~10 min par un cron externe hébergé sur notre serveur Azure, qui
// envoie l'en-tête `Authorization: Bearer $CRON_SECRET`. La cadence est configurée côté
// Azure (pas de vercel.json).
//
// Route sous /api/cron/keep-warm (convention Vercel Cron). Le rewrite `/api/:path*`
// de next.config.ts (phase `afterFiles` par défaut) ne s'applique qu'aux chemins SANS
// route de fichier : ce Route Handler, étant une route de fichier, a priorité et n'est
// donc PAS proxyfié vers Render — contrairement au reste de /api/*.
export async function GET(request: Request): Promise<Response> {
  // 1. Auth : exiger `Authorization: Bearer <CRON_SECRET>`, que le cron externe
  //    (Azure) doit envoyer. Sans secret, l'auth n'est ignorée qu'en dev local :
  //    sur Vercel, la route se ferme plutôt que de s'ouvrir à tous (#1021).
  const cronSecret = process.env.CRON_SECRET;
  if (!cronSecret && process.env.VERCEL_ENV) {
    console.error("[keep-warm] CRON_SECRET absent : route fermée");
    return NextResponse.json({ ok: false, error: "non configuré" }, { status: 503 });
  }
  if (cronSecret && !secretValide(request.headers.get("authorization"), cronSecret)) {
    return NextResponse.json({ ok: false, error: "non autorisé" }, { status: 401 });
  }

  // 2. Ping du backend avec timeout natif (ne pas laisser la fonction pendre).
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8001";
  const url = `${backendUrl}${HEALTH_PATH}`;
  const start = Date.now();

  try {
    // `cache: "no-store"` : chaque ping doit réellement toucher Render (jamais le
    // Data Cache de Next), sinon le keep-warm ne réveille rien. Cf. lib/api/server.ts.
    const res = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS), cache: "no-store" });
    const durationMs = Date.now() - start;

    if (!res.ok) {
      console.error(`[keep-warm] backend a répondu ${res.status} en ${durationMs}ms`);
      return NextResponse.json(
        { ok: false, error: `statut backend ${res.status}`, durationMs },
        { status: 502 },
      );
    }

    return NextResponse.json({ ok: true, backendStatus: res.status, durationMs });
  } catch (err) {
    const durationMs = Date.now() - start;
    const error =
      err instanceof Error
        // `AbortSignal.timeout` rejette avec un `TimeoutError`, là où un
        // `AbortController.abort()` rejetait avec un `AbortError`.
        ? err.name === "TimeoutError"
          ? "délai dépassé"
          : err.message
        : "erreur inconnue";
    console.error(`[keep-warm] échec du ping backend après ${durationMs}ms : ${error}`);
    return NextResponse.json({ ok: false, error, durationMs }, { status: 502 });
  }
}

/** Comparaison à temps constant : un `!==` fuit la longueur du préfixe commun. */
function secretValide(auth: string | null, secret: string): boolean {
  const recu = Buffer.from(auth ?? "");
  const attendu = Buffer.from(`Bearer ${secret}`);
  return recu.length === attendu.length && timingSafeEqual(recu, attendu);
}
