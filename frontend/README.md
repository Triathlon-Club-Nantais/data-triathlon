# frontend — TCN Résultats (Next.js)

Frontend Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui consommant
l'API backend `/api/v1`.

## Développement

```bash
cp .env.local.example .env.local   # BACKEND_URL / API_URL → backend
npm install
npm run dev                        # http://localhost:3000 (rewrites /api → :8001)
```

Backend requis : `uvicorn app.main:app --port 8001` depuis `backend/`.

## Scripts

- `npm run dev` — serveur de dev
- `npm run build` — build production (typage strict + RSC)
- `npm test` — tests Vitest + RTL
- `npm run lint` — ESLint

## Déploiement (Vercel)

- Projet Vercel pointant sur `frontend/`.
- Variables d'environnement :
  - `BACKEND_URL` — URL interne du backend Render (rewrites client).
  - `API_URL` — URL du backend pour les Server Components.
- CORS : ajouter le domaine Vercel à `CORS_ORIGINS` du backend.
