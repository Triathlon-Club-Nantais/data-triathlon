# Quickstart — Guide utilisateur intégré

## Prérequis

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000 (ou port suivant libre)
```

Backend dev lancé en parallèle (`uv run python scripts/dev_server.py` depuis
`backend/`) pour que le mot de passe de site et la session admin fonctionnent.

## Scénario 1 — Un membre atteint le guide en un clic

1. Ouvrir l'application, saisir le mot de passe de site si demandé.
2. Depuis la navigation principale, cliquer sur l'entrée « Guide » (section
   « Consulter »).
3. **Attendu** : `/guide` s'affiche, sommaire des 7 sections membres visible,
   chaque section porte des étapes concises et au moins une capture d'écran.
4. Cliquer sur un lien du sommaire (ex. « Bénévolat »).
5. **Attendu** : défilement direct vers `#benevolat`, sans rechargement de
   page.
6. Ouvrir `http://localhost:3000/guide#benevolat` dans un nouvel onglet
   (accès direct par URL, FR-010).
7. **Attendu** : la page s'ouvre positionnée sur la section « Bénévolat ».

## Scénario 2 — Un admin atteint le guide admin, un non-admin non

1. Se connecter avec un compte disposant d'une session admin (SSO).
2. Depuis l'espace admin, cliquer sur l'entrée « Guide ».
3. **Attendu** : `/admin/guide` s'affiche, sommaire des 16 sections admin,
   chacune avec étapes concises + capture d'écran à jour.
4. Se déconnecter, ou utiliser une session anonyme, et ouvrir
   `http://localhost:3000/admin/guide` directement.
5. **Attendu** : redirection/garde identique à toute autre page `app/admin/`
   (pas d'accès aux sections admin — FR-011), pas de fuite du contenu par
   URL directe.

## Refaire les captures (#926)

Le dépôt est public : une capture ne montre **jamais** de données réelles.

1. Base SQLite jetable, jamais celle du `.env` du backend : `DATABASE_URL=sqlite:///<chemin> uv run python scripts/reset_db.py --yes`.
2. Le seed importe de vrais résultats publics : remplacer ensuite `athletes.nom`, `athletes.prenom` et `participations.team_name` par des noms fictifs, et vider `participations.raw_data`.
3. Comptes fictifs en `@exemple.fr`, code d'accès posé par `set-site-code`. Peupler les écrans d'administration par l'API (groupes, variantes, retours, déclarations), ce qui remplit aussi le journal.
4. Front en **build de production** (`npm run build`, puis `npx next start` avec `API_URL` et `BACKEND_URL` vers ce backend), `NEXT_PUBLIC_APP_VERSION` et `APP_VERSION` posées : ni overlay Next, ni badge « dev ».
5. Horloge du serveur Next et du navigateur figée dans la saison des données, sinon les KPI de la saison en cours sont à zéro.
6. Navigateur en français, fenêtre 1418×840, capture JPEG.

## Vérification automatisée

```bash
cd frontend
npm test                 # Vitest — inclut page.test.tsx (2 pages) et guide-content.test.ts
npm run build             # build prod strict TS + RSC
npm run lint
```
