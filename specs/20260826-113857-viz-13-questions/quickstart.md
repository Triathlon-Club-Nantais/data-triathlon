# Quickstart — validation des 13 vues

## Prérequis

```bash
cd backend && uv sync && uv run alembic upgrade head
cd frontend && npm install
```

Deux serveurs, chacun dans son terminal, depuis la racine du worktree :

```bash
cd backend && uv run python scripts/dev_server.py   # API + /docs
cd frontend && npm run dev                          # branché sur ce backend
```

## Validation automatisée (à chaque US, avant de passer à la suivante)

```bash
cd backend && uv run pytest -m "not integration"   # TDD : rouge puis vert
cd frontend && npm test
cd frontend && npm run build                        # TS strict + RSC
uv run ruff check backend                            # lint backend
cd frontend && npm run lint                          # ESLint
```

## Scénarios de validation manuelle, un par US

Utiliser un athlète/club avec un historique réel (données de démo via
`uv run python scripts/reset_db.py`, ou base existante du worktree).

1. **US1** — `/athletes/[id]` d'un athlète ≥3 participations : la série de
   progression s'affiche ; sur un athlète à 1 participation, un état vide
   explicite s'affiche à la place.
2. **US2** — détail d'une participation : l'histogramme des temps de
   l'épreuve s'affiche avec un repère sur le temps de l'athlète.
3. **US3** — même écran : le classement en catégorie affiche « Nᵉ / M »
   avec une représentation visuelle.
4. **US4** — même écran : les écarts par segment sont visuels (pas
   seulement en pourcentage) ; sur la page profil, un signal de segment
   récurrent apparaît si applicable.
5. **US5** — même écran : un graphique de temps cumulés (allure) est
   disponible en complément du graphique de classement.
6. **US6** — page profil : sélectionner un second athlète du club et
   vérifier l'affichage comparatif ; tester aussi le cas sans épreuve
   commune (message explicite, pas de graphique vide).
7. **US7** — page profil d'un athlète multi-discipline/multi-saison : la
   répartition complète s'affiche, pas seulement le mode.
8. **US8** — `/dashboard`, changer de saison via `SeasonSelector` : le
   graphique de performance collective se met à jour.
9. **US9** — `/club` : la répartition genre/catégorie s'affiche.
10. **US10** — `/club` ou `/dashboard` : la performance par discipline
    (podiums) s'affiche, distincte du volume d'épreuves par discipline.
11. **US11** — `/resultats` : une vue de couverture mensuelle/annuelle
    précède ou complète la liste, avec les trous visibles.
12. **US12** — `/carte` : activer le filtre « à venir » (seules les
    épreuves futures restent) et vérifier le tri/filtre par distance.
13. **US13** — `/benevoles` : après au moins une validation/un rejet
    post-migration, le graphique d'arriéré et le délai moyen s'affichent ;
    avant toute résolution post-migration, état vide explicite.

## Responsive (RESP-2/#480, hérité — pas re-testé en profondeur par US)

Sur chaque écran touché, vérifier à 375 px de large qu'aucun graphique
ajouté ne descend sous le seuil de lisibilité déjà fixé par #480 (labels non
compressés, pas de texte sous ~10 px effectifs).

## Rendu serveur sans JavaScript

Sur au moins un écran par famille de graphique nouveau (SVG `d3-scale`/
`d3-shape`), vérifier que le contenu essentiel reste présent avec JS
désactivé — cohérent avec l'existant (`Histogram`, `CategoryBars`, etc.).
