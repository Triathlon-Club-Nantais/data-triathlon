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
  // 1. Auth : si CRON_SECRET est défini, exiger `Authorization: Bearer <secret>`.
  //    Le cron externe (Azure) doit envoyer cet en-tête ; sinon la requête est rejetée.
  //    En dev local (CRON_SECRET absent/vide), l'auth est ignorée pour tester manuellement.
  const cronSecret = process.env.CRON_SECRET;
  if (cronSecret) {
    const auth = request.headers.get("authorization");
    if (auth !== `Bearer ${cronSecret}`) {
      return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }
  }

  // 2. Ping du backend avec timeout via AbortController (ne pas laisser la fonction pendre).
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8001";
  const url = `${backendUrl}${HEALTH_PATH}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const start = Date.now();

  try {
    const res = await fetch(url, { signal: controller.signal });
    const durationMs = Date.now() - start;

    if (!res.ok) {
      console.error(`[keep-warm] backend a répondu ${res.status} en ${durationMs}ms`);
      return NextResponse.json(
        { ok: false, error: `backend status ${res.status}`, durationMs },
        { status: 502 },
      );
    }

    return NextResponse.json({ ok: true, backendStatus: res.status, durationMs });
  } catch (err) {
    const durationMs = Date.now() - start;
    const error =
      err instanceof Error
        ? err.name === "AbortError"
          ? "délai dépassé"
          : err.message
        : "erreur inconnue";
    console.error(`[keep-warm] échec du ping backend après ${durationMs}ms : ${error}`);
    return NextResponse.json({ ok: false, error, durationMs }, { status: 502 });
  } finally {
    clearTimeout(timer);
  }
}
