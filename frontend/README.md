# frontend — TCN Résultats (Next.js)

Frontend Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui consommant
l'API backend `/api/v1`.

## Développement

```bash
npm install
npm run dev                        # http://localhost:3000 (ou le port libre suivant)
```

Backend requis : `uv run python scripts/dev_server.py` depuis `backend/`.

`npm run dev` découvre son port dans `.dev-backend.json` (publié par le backend à la
racine du worktree) et renseigne `BACKEND_URL` + `API_URL` — le frontend parle donc
toujours au backend de **son** worktree. Lancé avant le backend, il l'attend.
Pour viser un autre backend, définir `BACKEND_URL` (ou le poser dans `.env.local`,
cf. `.env.local.example`) : la découverte est alors court-circuitée.

## Scripts

- `npm run dev` — serveur de dev (découverte du backend + `next dev`)
- `npm run dev:next` — `next dev` brut, sans découverte
- `npm run build` — build production (typage strict + RSC)
- `npm test` — tests Vitest + RTL
- `npm run lint` — ESLint

## Déploiement (Vercel)

- Projet Vercel pointant sur `frontend/`.
- Variables d'environnement :
  - `BACKEND_URL` — URL interne du backend Render (rewrites client).
  - `API_URL` — URL du backend pour les Server Components.
- CORS : ajouter le domaine Vercel à `CORS_ORIGINS` du backend.
