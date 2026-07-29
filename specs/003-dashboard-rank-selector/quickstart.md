# Quickstart — Sélecteur de type de rang

**Feature** : `feat/104-dashboard-rank-selector`
**Public** : contributeur qui veut valider la feature de bout en bout, sans lire tout le plan.

## Ce qu'on livre

Un toggle 4-boutons **Scratch / Catégorie / Genre / Tous** sur `/dashboard` et `/club`. Il pilote la sémantique des cartes de stats (Victoires / Podiums / Top 10) et de la liste des podiums récents de `/club`. Défaut : Scratch.

## Vérifier en dev

```bash
# 1. Repartir de la branche de la feature
git checkout feat/104-dashboard-rank-selector

# 2. Backend + Frontend en parallèle (dans deux terminaux)
cd backend  && uv run python scripts/dev_server.py
cd frontend && npm run dev
```

Le frontend démarre sur `http://localhost:3000`, le backend est piqué automatiquement via `.dev-backend.json`.

## Parcours utilisateur (7 URLs à ouvrir)

| # | URL | Attendu observable |
|---|---|---|
| 1 | `http://localhost:3000/dashboard` | Toggle affiché, bouton « Scratch » actif. Les 3 cartes reflètent le décompte scratch. Libellé secondaire : « scratch ». |
| 2 | `http://localhost:3000/dashboard?rank=category` | Bouton « Catégorie » actif. Cartes recalculées sur `rank_category`. Libellé : « catégorie ». |
| 3 | `http://localhost:3000/dashboard?rank=gender` | Bouton « Genre » actif. Chaque carte affiche **deux compteurs** : F et H, côte à côte, jamais confondus. |
| 4 | `http://localhost:3000/dashboard?rank=all` | Bouton « Tous » actif. Cartes reprennent exactement les valeurs pré-feature (avant merge de la PR). Libellé : « scratch, genre ou catégorie ». |
| 5 | `http://localhost:3000/dashboard?rank=foo` | Retombe silencieusement sur « Scratch ». Aucune erreur, aucune redirection. |
| 6 | `http://localhost:3000/club?rank=scratch` | Liste « Podiums & performances » ne montre que les podiums scratch (badge « Général » partout). |
| 7 | `http://localhost:3000/club?rank=category` | Liste ne montre que les podiums catégorie (badge « Catégorie »). |

**Composition avec les filtres existants** — à vérifier au moins une fois :

- `http://localhost:3000/dashboard?rank=scratch&seasons=2025-2026` → toggle rank sur « Scratch », toggle saison sur 2025-2026. Les deux filtres s'appliquent.
- `http://localhost:3000/club?rank=all&sports=all` → tous rangs mélangés + disciplines fédérales et hors fédération.

## Vérifier en tests

```bash
cd frontend
npm test                                   # 199+ verts (nouveaux cas inclus)
npm test -- lib/rank                       # tests du parseur seul
npm test -- club-aggregate                 # tests des fonctions de comptage
npm test -- RankTypeToggle                 # tests du composant
npm run lint                               # 0 warnings
npm run build                              # build prod strict OK
```

## Ce qui **n'est pas** modifié

- Fiche athlète (`/athletes/[id]`) — a sa propre logique, hors périmètre.
- Endpoint `/api/v1/*` — aucun paramètre backend nouveau.
- Schéma DB — inchangé.
- Composant `DisciplineToggle` (le toggle des disciplines) — reste tel quel, `RankTypeToggle` coexiste à côté.

## Points de contrôle avant merge

- [ ] Les 4 modes produisent chacun un rendu correct sur `/dashboard` et `/club`.
- [ ] Un lien `?rank=X` copié-collé rouvre la page dans le même état (partage).
- [ ] Un lien historique `/dashboard` (sans `?rank=`) rouvre en mode « Scratch », pas en « Tous » — changement de défaut assumé.
- [ ] La liste des podiums de `/club` est bien filtrée en mode Scratch / Catégorie / Genre.
- [ ] Le mode Tous préserve exactement les valeurs affichées avant la feature.
- [ ] Un athlète sans genre en base n'est pas compté dans le mode Genre.
