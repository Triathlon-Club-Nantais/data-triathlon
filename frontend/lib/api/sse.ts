import { ApiError, messageDErreur } from "@/lib/api/client";
import type {
  ImportProgressEvent,
  RescrapeProgressEvent,
  SwitchSourceProgressEvent,
} from "@/lib/types";

const BASE = "/api/v1";

/** Lecteur SSE générique — patron partagé par l'import public et le re-scrape admin (#118). */
async function* readEventStream<T>(res: Response): AsyncGenerator<T> {
  if (!res.body) {
    throw new Error("Erreur lors du démarrage du flux");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      if (part.startsWith("data: ")) {
        try {
          yield JSON.parse(part.slice(6)) as T;
        } catch {
          /* frame incomplète ou bruit : ignorer */
        }
      }
    }
  }
}

export async function* importEventStream(
  url: string,
  signal?: AbortSignal,
  singleHeat: boolean = true,
): AsyncGenerator<ImportProgressEvent> {
  const res = await fetch(`${BASE}/scrape/event/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, single_heat: singleHeat }),
    signal,
  });
  // Même patron que `rescrapeEventStream` ci-dessous : un refus arrive **avant**
  // le premier octet du flux, corps JSON `{"detail": "..."}`. Le lire n'est plus
  // du confort depuis le plafond de débit (#395) — « Erreur lors du démarrage de
  // l'import » sur un 429 laisserait le visiteur réessayer indéfiniment au lieu
  // de lui dire d'attendre.
  //
  // `ApiError` et non `Error` nu (#491) : le statut est la seule chose qui
  // distingue « plafond atteint », « service muet » et « page illisible », et
  // l'écran doit les traiter différemment — seul le dernier est un défaut de
  // fournisseur à signaler au back-office.
  if (!res.ok || !res.body) {
    const corps = await res.json().catch(() => null);
    const attente = Number(res.headers.get("Retry-After"));
    throw new ApiError(
      res.status,
      // `messageDErreur` et non `corps.detail` : sur un 422, FastAPI rend une
      // **liste** d'objets, qui s'affichait « [object Object] » dans l'alerte.
      messageDErreur(corps?.detail, "Erreur lors du démarrage de l'import"),
      Number.isFinite(attente) && attente > 0 ? attente : null,
    );
  }
  yield* readEventStream<ImportProgressEvent>(res);
}

/**
 * Flux SSE du re-scrape à la demande d'une course (#118).
 *
 * Un 404/409 (course introuvable, sans source active, ou déjà en cours de
 * re-scrape) arrive **avant** tout octet du flux — la route l'évalue
 * synchroniquement avant d'ouvrir le `StreamingResponse` (contrat backend,
 * `admin_course_rescrape.py`) — donc `res.ok` suffit à les distinguer du
 * chemin heureux, corps JSON `{"detail": "..."}` lu pour le message.
 */
export async function* rescrapeEventStream(
  courseId: number,
): AsyncGenerator<RescrapeProgressEvent> {
  const res = await fetch(`${BASE}/admin/courses/${courseId}/rescrape`, {
    method: "POST",
  });
  if (!res.ok) {
    const corps = await res.json().catch(() => null);
    throw new ApiError(
      res.status,
      messageDErreur(corps?.detail, "Erreur lors du démarrage du re-scrape"),
    );
  }
  yield* readEventStream<RescrapeProgressEvent>(res);
}

/**
 * Flux SSE de la bascule de source active d'une épreuve (#285, #624).
 *
 * Un 400 (`is_active: false`, refus toujours synchrone) ou un 404
 * (course/source introuvable) arrive **avant** tout octet du flux — même
 * contrat que `rescrapeEventStream` ci-dessus (`admin_course_sources.py`) —
 * donc `res.ok` suffit à les distinguer du chemin heureux, corps JSON
 * `{"detail": "..."}` lu pour le message.
 */
export async function* switchSourceEventStream(
  courseId: number,
  sourceId: number,
): AsyncGenerator<SwitchSourceProgressEvent> {
  const res = await fetch(`${BASE}/admin/courses/${courseId}/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_active: true }),
  });
  if (!res.ok) {
    const corps = await res.json().catch(() => null);
    throw new ApiError(
      res.status,
      messageDErreur(corps?.detail, "Erreur lors du démarrage de la bascule"),
    );
  }
  yield* readEventStream<SwitchSourceProgressEvent>(res);
}
