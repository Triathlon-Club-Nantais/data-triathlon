# Quickstart — Recherche d'athlète toujours accessible et sélection explicite

## Prérequis

```bash
cd backend && uv run python scripts/dev_server.py   # API, port publié
cd frontend && npm run dev                          # Next.js, branché dessus
```

Base dev SQLite avec au moins un athlète existant (`uv run python scripts/reset_db.py` sinon).

## Scénarios à valider manuellement (reflètent les Acceptance Scenarios de `spec.md`)

1. **Recherche visible sans sélection, rail déplié** — ouvrir l'app, déplier
   le rail (bouton en haut à gauche). Le bouton "Rechercher un athlète"
   (icône loupe + libellé + raccourci) est visible et cliquable.

2. **Recherche + tuile coexistent, rail déplié** — via ce bouton, choisir un
   athlète. Vérifier que l'entrée "Rechercher un athlète" reste affichée en
   plus de la tuile de l'athlète retenu (aucune des deux ne remplace l'autre).

3. **Recherche accessible, rail replié, athlète retenu** — replier le rail.
   Vérifier qu'une icône de recherche reste visible et cliquable, en plus de
   la tuile athlète (icône seule elle aussi).

4. **Raccourci clavier** — depuis n'importe quel écran, presser `⌘K` (Mac) ou
   `Ctrl+K` (autre). La recherche s'ouvre.

5. **Sélection depuis le profil** — ouvrir la page d'un athlète non retenu
   (`/athletes/{id}`). Cliquer sur le bouton de sélection. Vérifier que la
   navigation reflète immédiatement ce choix (tuile mise à jour, sans
   rechargement de page).

6. **Bascule sélection ↔ relâchement** — revenir sur la page de ce même
   athlète (désormais retenu). Le bouton propose "Relâcher" au lieu de
   "Sélectionner". Cliquer dessus : la navigation repasse à l'état "aucun
   athlète retenu", toujours sans rechargement.

7. **Format mobile** — réduire la fenêtre sous le point de rupture `md`.
   Vérifier que le bouton loupe de la barre mobile reste inchangé et que
   l'athlète retenu, s'il y en a un, apparaît en complément dans le tiroir
   (panneau déplié), sans dupliquer l'accès recherche.

## Tests automatisés

```bash
cd frontend
npm test                # Vitest — couvre AppNav.test.tsx et athletes/[id]/page.test.tsx étendus
```
