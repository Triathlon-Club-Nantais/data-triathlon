# Phase 0 Research: Page de résultats détaillée d'une participation

## 1. Liste des fournisseurs éligibles (FR-003)

**Decision** : la liste "fiable pour la complétude des splits" est une liste
d'exclusion — tous les fournisseurs sont éligibles sauf ceux identifiés
ci-dessous comme partiels, plus le fournisseur `manuel` toujours exclu.

**Non éligibles** (splits incomplets pour l'ensemble des finishers) :

| Fournisseur | Preuve |
|---|---|
| `t2area` | `docs/scrapers/t2area.md` + `t2area.py:526` (`if not is_tcn(resultat.club): continue`) — les splits ne sont scrapés que sur la fiche individuelle des membres TCN. |
| `breizhchrono` | `breizhchrono.py:223,280-299` (`_fetch_tcn_fine_splits`) — les splits fins par segment ne sont re-fetchés/appliqués que `if is_tcn(r.club)`; les autres finishers ne gardent que des inter-splits grossiers. **Non documenté dans `docs/scrapers/`** (seulement en commentaire de code) — c'est un angle mort de la doc provider, distinct du sujet de cette feature ; à signaler séparément, pas à corriger ici. |

**Éligibles** (un seul passage scrape les splits de tous les finishers, aucun
filtre `is_tcn` trouvé dans le module) : `klikego`, `raceresult`, `oktime`,
`sporthive`, `chronoweb`, `wiclax`, `chronoplace`, `runnerbreizh`, `timepulse`,
`prolivesport`, `sportinnovation`, `competitor`.

**Alternatives considered** :
- Liste d'inclusion (blanche) plutôt que d'exclusion : rejetée — une liste
  blanche se périme silencieusement à chaque nouveau fournisseur enregistré
  dans `registry.py` (le nouveau fournisseur resterait non éligible par
  défaut sans qu'on y pense) ; l'exclusion, elle, échoue de façon visible
  (trop permissive) plutôt que de façon silencieuse (trop restrictive) —
  préférable pour une fonctionnalité qui n'est qu'un affichage enrichi, pas
  une garde de sécurité.
- Vérification dynamique de complétude (compter les finishers avec splits
  vides) : écartée en clarification (voir spec.md, décision du 2026-08-13) —
  hors scope de ce premier lot, la liste en code suffit et les deux cas
  connus sont déjà identifiés par fournisseur, pas par course.

**Notes annexes** (non bloquantes pour ce plan, à documenter ailleurs) :
- `runnerbreizh` ne publie jamais de transitions (T1/T2 structurellement
  absentes pour tout le monde) — couvert par FR-013 (n'afficher que les
  segments publiés), pas une raison d'exclusion.
- `competitor` ne publie aucun club (`club = ""`) — sans effet ici puisque la
  restriction club a été levée (FR-004), mentionné pour mémoire.

## 2. Récupération du classement complet d'une course

**Decision** : réutiliser `participation_repository.list_for_course(db, course_id)`
(`backend/app/repositories/participation_repository.py:292`) — retourne déjà
tous les `Participation` ORM d'une course, athlète chargé en eager
(`joinedload`), triés par rang. C'est le point d'entrée du nouveau service de
calcul.

**Rationale** : déjà réutilisé par un service existant (`import_service.py`)
pour les mêmes besoins de "tout le classement, objets complets" ; évite de
dupliquer une requête déjà écrite, conforme à `list_page_for_course(...,
page_size=None)` qui est la variante API (`page_size=all`) mais retourne des
tuples plus légers — inadaptés ici car il faut `.splits` et `.athlete` par
ligne.

**Alternatives considered** : requête dédiée dans le nouveau service —
rejetée, redondante avec une méthode de repository déjà testée et en place
(Principe VI, YAGNI).

## 3. Arithmétique sur les temps

**Decision** : réutiliser `app/scrapers/utils.py::to_seconds` /
`fmt_seconds`, déjà importés hors de `scrapers/` par `stats_service.py`. Le
nouveau calcul (classement par segment, simulation d'amélioration) est une
logique **entièrement nouvelle** à écrire dans le nouveau service : aucune
fonction existante ne classe des participations par temps de segment ni ne
simule une réduction de pourcentage sur une durée — `rank_overall` /
`rank_category` / `rank_gender` sont précalculés à l'import par chaque
scraper, jamais recalculés à la lecture.

**Rationale** : `to_seconds`/`fmt_seconds` unifient déjà 6 implémentations
dupliquées (klikego, timepulse, wiclax, chronoweb, oktime, stats_service) —
les réutiliser plutôt que reparser les strings est la voie déjà tracée par le
projet.

## 4. Graphique d'évolution du classement (frontend)

**Decision** : composant SVG à la main, sur le même patron que `Histogram`
(`frontend/app/courses/[id]/page.tsx:199-257`) — `viewBox` fixe, `width:
100%`, axes et graduations dessinées à la main, couleurs via les tokens CSS
existants. Aucune librairie de charting n'est présente dans
`frontend/package.json` et aucune n'est nécessaire pour ce graphique à deux
séries sur cinq étapes.

**Rationale** : cohérent avec Principe VI (ne pas ajouter de dépendance pour
un besoin déjà couvert par un patron existant) et avec la spec PDF qui exige
explicitement un SVG `viewBox="0 0 600 360"`, pas un composant de librairie.

**Nouveau** : l'interaction d'infobulle au survol (position par étape) n'a
aucun précédent dans le codebase (aucun `onMouseEnter`/`onMouseMove` sur un
graphique existant) — à construire spécifiquement pour cette feature, en
suivant le comportement détaillé de la spec PDF (rectangle 178×48px,
positionnement adaptatif gauche/droite selon l'abscisse, une seule infobulle
visible à la fois).

**Alternatives considered** : ajouter une librairie de charting (recharts/
visx) pour bénéficier de tooltips prêts à l'emploi — écartée, le graphique
est trop simple (2 séries, 5 points) pour justifier une nouvelle dépendance
sur un projet qui n'en a aucune à ce jour.

## 5. Jetons de design

**Decision** : aucun nouveau jeton de couleur/typographie nécessaire pour les
éléments déjà couverts — `--tcn-orange`, `--tcn-ink`, `--tcn-paper`,
`--tcn-font-display` (Anton), `--tcn-font-body` (Barlow), `--tcn-font-cond`
(Barlow Semi Condensed) existent déjà dans `frontend/app/globals.css` et sont
déjà utilisés par `RaceFinishers.tsx`. Seul manque un jeton de couleur dédié
pour T1/T2 (aujourd'hui seuls swim/bike/run ont un alias de couleur ;
transitions actuellement rendues en gris atténué "texte secondaire" — cohérent
avec le "En-tête orange pour Natation/Vélo/Course, gris pour T1/T2" de la spec
PDF, donc pas un manque réel : le traitement voulu est déjà celui du gris
existant).

**Rationale** : réutilisation systématique évite de fragmenter le système de
design (Principe VI).

## 6. Convention de test pour le nouveau service

**Decision** : suivre les deux conventions déjà en place dans
`backend/tests/test_services/` plutôt que d'en introduire une troisième :
- Logique pure (classement par segment, matrice de comparaison, simulation de
  gains) : testée avec des fakes `types.SimpleNamespace` sans session DB, à la
  `test_quality.py` — rapide, aucune dépendance réseau (Principe III).
- Récupération du classement complet + intégration bout en bout : un test
  `db_session` à la `test_stats_service.py`, avec les mêmes helpers `_seed`/
  `_epreuve` que le service voisin, pour vérifier l'assemblage complet
  (repository → service → forme de sortie).

**Rationale** : les deux services (`stats_service`, ce nouveau service)
répondent au même besoin — un agrégat calculé à la demande sur toute une
course — la convention de test existante s'applique donc telle quelle.

## 7. Remplacement du clic de ligne existant (résolution FR-001/FR-002)

**Decision** : le clic sur une ligne de finisher (page course) ou sur une
ligne d'épreuve (page athlète) navigue **systématiquement** vers la nouvelle
page de détail — y compris quand la course n'est pas éligible, auquel cas la
page affiche l'état "statistiques indisponibles" (FR-005) plutôt que d'être
court-circuitée. Les deux comportements actuels (ligne de course → profil
athlète ; ligne d'athlète → page course) sont remplacés, pas conservés en
parallèle.

**Rationale** : la spec fonctionnelle PDF jointe à l'issue #272 (section 1.1
« Points d'entrée ») documente explicitement les deux entrées — « Résultats
athlète : clic sur une ligne d'épreuve » et « Résultats triathlon : clic sur
une ligne de finisher », toutes deux transmettant `athlete` + `course` vers ce
même écran — et section 2 (« Les deux états de la page ») confirme que l'état
indisponible est un rendu de **cette page**, pas une redirection évitée en
amont. C'est une lecture directe d'une source déjà fournie et faisant foi
(cf. spec.md, Assumptions), pas une nouvelle clarification à ouvrir.

**Alternatives considered** : ajouter la nouvelle page comme action
supplémentaire à côté du clic existant (ex. une icône dédiée), en gardant les
deux anciennes navigations intactes — rejetée, contredit la spec PDF fournie
et ajoute une action de plus dans une interface déjà dense (tableau de
finishers) sans que le produit l'ait demandé.
