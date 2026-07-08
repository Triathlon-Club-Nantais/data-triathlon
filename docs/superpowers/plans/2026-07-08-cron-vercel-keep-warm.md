# Cron Vercel « keep-warm » — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une Route Handler Next.js `/cron/keep-warm` qui ping `${BACKEND_URL}/api/v1/health`, planifiée par un cron Vercel toutes les 10 min, pour empêcher le cold start du backend Render.

**Architecture:** Une Route Handler `GET` sous `frontend/app/cron/keep-warm/route.ts` (hors `/api/` pour éviter le rewrite `next.config.ts`). Elle vérifie un secret optionnel (`CRON_SECRET`), relaie un `fetch` avec timeout `AbortController` vers l'endpoint de santé du backend, et renvoie `200`/`401`/`502`. Un `frontend/vercel.json` déclare le cron `*/10 * * * *`. Le secret est documenté dans `.env.local.example`.

**Tech Stack:** Next.js 16 (App Router, Route Handlers), TypeScript strict, Vitest 4, Vercel Cron Jobs.

## Global Constraints

- **UI, commentaires et messages en français** (avec accents).
- **Route hors de `/api/`** : `next.config.ts` réécrit `/api/:path*` vers le backend Render → utiliser `/cron/keep-warm`.
- **Rendu dynamique obligatoire** : `export const dynamic = "force-dynamic"` (pas de cache statique).
- **Timeout du `fetch` backend ≈ 10 s** via `AbortController`.
- **Ne jamais committer la vraie valeur de `CRON_SECRET`** — placeholder uniquement.
- **Endpoint cible** : `${BACKEND_URL}/api/v1/health` (un seul endpoint, YAGNI).
- **Planification cron** : `*/10 * * * *` (cible Vercel Pro) ; documenter la limite Hobby (1 exéc/jour) + alternative externe (cron-job.org / UptimeRobot).
- **Tests unitaires sans réseau** : `fetch` global mocké via `vi.stubGlobal`.
- Commits : Conventional Commits (`feat:`…).
- Travailler depuis le worktree courant ; toutes les commandes frontend s'exécutent depuis `frontend/`.

---

## File Structure

| Fichier | Rôle |
|---------|------|
| `frontend/app/cron/keep-warm/route.ts` | **Créer** — Route Handler `GET` : auth optionnelle, ping backend avec timeout, réponses `200/401/502`. |
| `frontend/app/cron/keep-warm/route.test.ts` | **Créer** — Tests Vitest (401, 200, 502 non-2xx, 502 réseau, dev sans secret). |
| `frontend/vercel.json` | **Créer** — Déclaration du cron Vercel `*/10 * * * *` → `/cron/keep-warm`. |
| `frontend/.env.local.example` | **Modifier** — Ajouter le placeholder `CRON_SECRET` + note limite Hobby / alternative. |

Deux tâches :
1. **Task 1** — Route Handler + tests (le cœur, TDD). Deliverable testable de bout en bout.
2. **Task 2** — Câblage cron Vercel (`vercel.json`) + documentation d'environnement. Config/doc, vérifiée par `npm run build` et relecture.

---

### Task 1: Route Handler `/cron/keep-warm`

**Files:**
- Create: `frontend/app/cron/keep-warm/route.ts`
- Test: `frontend/app/cron/keep-warm/route.test.ts`

**Interfaces:**
- Consumes : `process.env.BACKEND_URL` (déjà utilisé par `next.config.ts`, défaut `http://localhost:8001`), `process.env.CRON_SECRET` (optionnel).
- Produces : `export async function GET(request: Request): Promise<Response>` et `export const dynamic = "force-dynamic"`. Réponses JSON :
  - `200` → `{ ok: true, backendStatus: number, durationMs: number }`
  - `401` → `{ ok: false, error: "unauthorized" }`
  - `502` → `{ ok: false, error: string, durationMs: number }`

**Notes d'implémentation clés :**
- Lire `CRON_SECRET` et `BACKEND_URL` **à l'intérieur** de `GET` (pas en constante de module) pour que `vi.stubEnv` fonctionne dans les tests.
- `CRON_SECRET` **falsy** (absent ou chaîne vide) → auth ignorée (dev local).
- Passer `{ signal }` de l'`AbortController` à `fetch` et nettoyer le `setTimeout` dans un `finally`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `frontend/app/cron/keep-warm/route.test.ts` :

```ts
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
  return new Request("http://localhost/cron/keep-warm", { headers });
}

describe("GET /cron/keep-warm", () => {
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
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run (depuis `frontend/`) : `npm test -- app/cron/keep-warm/route.test.ts`
Expected : FAIL — le module `./route` n'existe pas (erreur d'import/résolution).

- [ ] **Step 3: Écrire l'implémentation minimale**

Créer `frontend/app/cron/keep-warm/route.ts` :

```ts
import { NextResponse } from "next/server";

// Rendu dynamique : le ping doit s'exécuter à chaque appel, jamais mis en cache statiquement.
export const dynamic = "force-dynamic";

const HEALTH_PATH = "/api/v1/health";
const TIMEOUT_MS = 10_000;

// Cron Vercel « keep-warm » : maintient le backend Render éveillé (évite le cold start ~15 min).
//
// Planification : `*/10 * * * *` (voir vercel.json) — NÉCESSITE le plan Vercel Pro.
// En plan Hobby, les crons sont plafonnés à 1 exécution/jour (insuffisant). Alternative
// pour rester en Hobby : cron externe (cron-job.org / UptimeRobot) pointant sur cette route.
export async function GET(request: Request): Promise<Response> {
  // 1. Auth : si CRON_SECRET est défini, exiger `Authorization: Bearer <secret>`.
  //    Vercel injecte automatiquement cet en-tête sur les crons quand CRON_SECRET existe.
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
    const error = err instanceof Error ? err.message : "erreur inconnue";
    console.error(`[keep-warm] échec du ping backend après ${durationMs}ms : ${error}`);
    return NextResponse.json({ ok: false, error, durationMs }, { status: 502 });
  } finally {
    clearTimeout(timer);
  }
}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run (depuis `frontend/`) : `npm test -- app/cron/keep-warm/route.test.ts`
Expected : PASS (5 tests verts).

- [ ] **Step 5: Vérifier le lint**

Run (depuis `frontend/`) : `npm run lint`
Expected : aucune erreur ESLint sur les nouveaux fichiers.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/cron/keep-warm/route.ts frontend/app/cron/keep-warm/route.test.ts
git commit -m "feat(cron): route handler keep-warm ping le backend Render"
```

---

### Task 2: Cron Vercel + documentation d'environnement

**Files:**
- Create: `frontend/vercel.json`
- Modify: `frontend/.env.local.example`

**Interfaces:**
- Consumes : la route `GET /cron/keep-warm` produite par Task 1.
- Produces : configuration cron Vercel (`crons[].path = "/cron/keep-warm"`, `schedule = "*/10 * * * *"`) et documentation du secret `CRON_SECRET`.

**Note :** `vercel.json` est du JSON strict — **pas de commentaires possibles**. La note sur la limite Hobby / l'alternative externe vit donc dans l'en-tête de `route.ts` (Task 1) et dans `.env.local.example` (ci-dessous).

- [ ] **Step 1: Créer `frontend/vercel.json`**

```json
{
  "crons": [
    {
      "path": "/cron/keep-warm",
      "schedule": "*/10 * * * *"
    }
  ]
}
```

- [ ] **Step 2: Documenter `CRON_SECRET` dans `.env.local.example`**

Ouvrir `frontend/.env.local.example` et **ajouter à la fin** (en conservant les lignes existantes, dont `BACKEND_URL`) le bloc suivant :

```dotenv

# Secret partagé du cron « keep-warm » (frontend/app/cron/keep-warm/route.ts).
# Vercel injecte automatiquement `Authorization: Bearer $CRON_SECRET` sur les invocations cron.
# Générer une valeur : openssl rand -hex 32 — à renseigner dans Vercel > Settings > Environment Variables.
# NE JAMAIS committer la vraie valeur ; laissée vide en local => auth du cron ignorée.
#
# Planification `*/10 * * * *` (vercel.json) => nécessite le plan Vercel Pro.
# En plan Hobby (1 cron/jour max), utiliser un cron externe (cron-job.org / UptimeRobot)
# pointant sur https://<domaine>/cron/keep-warm avec le même en-tête Authorization.
CRON_SECRET=
```

- [ ] **Step 3: Vérifier que le build accepte la config**

Run (depuis `frontend/`) : `npm run build`
Expected : build prod OK, la route `/cron/keep-warm` apparaît comme route dynamique (`ƒ`) dans la sortie de build, aucune erreur TypeScript.

- [ ] **Step 4: Vérifier que la suite de tests reste verte**

Run (depuis `frontend/`) : `npm test`
Expected : PASS (tous les tests existants + les 5 nouveaux).

- [ ] **Step 5: Commit**

```bash
git add frontend/vercel.json frontend/.env.local.example
git commit -m "feat(cron): planifie le cron Vercel keep-warm et documente CRON_SECRET"
```

---

## Self-Review

**1. Spec coverage :**
- Route Handler `/cron/keep-warm` `GET`, hors `/api/`, `force-dynamic` → Task 1. ✅
- Auth `CRON_SECRET` optionnelle, `401` si mauvais/absent en présence du secret, ignorée sans secret → Task 1 (impl + tests 401 & dev). ✅
- Ping `${BACKEND_URL}/api/v1/health` avec timeout `AbortController` ~10 s → Task 1. ✅
- Réponses `200 {ok,backendStatus,durationMs}` / `502 {ok,error,durationMs}` + `console.error` → Task 1. ✅
- Tests Vitest 401 / 200 / 502 (non-2xx & réseau) / dev sans secret, `fetch` mocké → Task 1 Step 1. ✅
- Planification `*/10 * * * *` (cible Pro) + doc limite Hobby + alternative externe → `vercel.json` (Task 2) + commentaires `route.ts` (Task 1) + `.env.local.example` (Task 2). ✅
- `CRON_SECRET` placeholder dans la doc d'env, jamais la vraie valeur, `BACKEND_URL` déjà présent → Task 2 Step 2. ✅
- Hors périmètre (métriques, multi-endpoints, retry interne) → non implémentés. ✅

**2. Placeholder scan :** Chaque step de code contient le code complet (route, tests, JSON, dotenv). Aucun « TODO / à compléter ». ✅

**3. Type consistency :** `GET(request: Request): Promise<Response>` et `dynamic` sont cohérents entre l'implémentation (Task 1 Step 3), les tests (Step 1) et le bloc Interfaces. Le `path` du cron (`/cron/keep-warm`) correspond au dossier `app/cron/keep-warm/`. ✅

**Note de vérification factuelle :** `.env.local.example` étant protégé en lecture dans cet environnement, Task 2 Step 2 procède par **ajout** en préservant l'existant (plutôt qu'un remplacement exact). L'exécutant doit conserver la ligne `BACKEND_URL` déjà présente.
