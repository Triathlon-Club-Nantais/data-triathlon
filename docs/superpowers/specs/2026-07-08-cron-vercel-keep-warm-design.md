# Cron Vercel « keep-warm » du backend Render

**Date** : 2026-07-08
**Branche** : `worktree-vercel-cron-keep-warm`
**Statut** : Design validé

## Problème

Le backend FastAPI est déployé sur **Render**. Sur l'offre gratuite, le service
s'endort après ~15 min d'inactivité et subit un **cold start** (plusieurs
secondes) à la première requête suivante. On veut réduire cet effet en gardant
le backend chaud via un **cron Vercel** (côté frontend Next.js) qui ping
périodiquement l'endpoint de santé `/api/v1/health`.

## Objectif

Un cron sur notre serveur Azure appellera toutes les ~10 min une Route Handler Next.js dédiée, qui
relaie un `fetch` vers `${BACKEND_URL}/api/v1/health` pour réveiller / maintenir
éveillé le backend Render.

## Contrainte de plan (importante)

- La planification `*/10 * * * *` (toutes les 10 min) **nécessite Vercel Pro**.
- En plan **Hobby**, les crons Vercel sont plafonnés à **1 exécution/jour**
  (granularité horaire) — insuffisant pour empêcher le cold start Render.
- Décision : on configure `*/10` (cible Pro) et on **documente la limite Hobby**
  en commentaire, avec l'alternative externe (cron-job.org / UptimeRobot) pour
  qui reste sur Hobby.

## Architecture

Deux artefacts, tous dans `frontend/`.

### 1. `frontend/app/api/cron/keep-warm/route.ts`

Route Handler Next.js (méthode `GET`).

**Choix de chemin — `/api/cron/keep-warm`** (convention Vercel Cron) :
`next.config.ts` réécrit `/api/:path*` vers le backend Render via un rewrite en
phase `afterFiles` (comportement par défaut de `rewrites()`). Ces rewrites ne
s'appliquent qu'aux chemins **sans route de fichier** : ce Route Handler, étant
une route de fichier, a priorité sur le rewrite et s'exécute **localement** — le
reste de `/api/*` continue d'être proxyfié vers Render. Vérifié au runtime :
`/api/cron/keep-warm` renvoie la réponse du handler local (401/502) tandis que
`/api/v1/health` est bien relayé au backend.

Comportement :

1. **Auth** : lit l'en-tête `Authorization`. Si `CRON_SECRET` est défini et que
   l'en-tête ne vaut pas `Bearer ${CRON_SECRET}` → réponse `401`. Vercel injecte
   automatiquement cet en-tête sur les invocations cron quand `CRON_SECRET`
   existe dans les variables d'environnement du projet.
   - Si `CRON_SECRET` n'est pas défini (dev local), l'auth est **ignorée** pour
     permettre de tester la route manuellement.
2. **Ping** : `fetch(${BACKEND_URL}/api/v1/health)` avec un **timeout** via
   `AbortController` (~10 s) pour ne pas laisser la fonction serverless pendre.
3. **Réponse** :
   - Succès → `200` avec `{ ok: true, backendStatus, durationMs }`.
   - Backend en erreur / timeout / injoignable → `502` avec
     `{ ok: false, error, durationMs }` + `console.error`. L'échec n'empêche pas
     le prochain ping planifié.

Le handler force le rendu dynamique (`export const dynamic = "force-dynamic"`)
pour ne pas être mis en cache statiquement.

### 1. Documentation d'environnement

- Ajouter `CRON_SECRET` (placeholder) à la doc frontend / `.env.example` s'il
  existe. **Ne jamais committer la vraie valeur.**
- `BACKEND_URL` existe déjà (utilisé par `next.config.ts`).
- Génération du secret : `openssl rand -hex 32` (ou base64 / `crypto.randomBytes`),
  à renseigner dans Vercel → Settings → Environment Variables.

## Flux

```
Cron Azure (~10 min) ─GET─▶ /api/cron/keep-warm  (Authorization: Bearer $CRON_SECRET)
                              │  vérifie le secret (401 sinon)
                              └──fetch(timeout 10s)──▶ ${BACKEND_URL}/api/v1/health
                                                        (réveille / garde chaud Render)
```

## Gestion d'erreurs

| Cas | Réponse | Effet |
|-----|---------|-------|
| Secret manquant/incorrect (avec `CRON_SECRET` défini) | `401` | Appel rejeté |
| Backend renvoie non-2xx | `502` + log | Ping échoué, retry au prochain cron |
| Timeout (>10 s) / réseau | `502` + log | Idem |
| Succès | `200` `{ ok, backendStatus, durationMs }` | Backend chaud |

## Tests (Vitest)

Test unitaire de la Route Handler, `fetch` global mocké :

1. **401** — `CRON_SECRET` défini, en-tête `Authorization` absent ou erroné.
2. **200** — secret correct, backend mocké renvoie `200` → réponse `{ ok: true }`
   et `fetch` appelé avec l'URL `${BACKEND_URL}/api/v1/health`.
3. **502** — backend mocké renvoie une erreur (ou `fetch` rejette) → `{ ok: false }`.
4. (Optionnel) **dev sans secret** — `CRON_SECRET` non défini → auth ignorée,
   ping tenté.

## Hors périmètre (YAGNI)

- Pas de métriques / persistance des pings.
- Pas de multi-endpoints (un seul `/api/v1/health`).
- Pas de retry interne : Vercel relance au prochain créneau cron.
