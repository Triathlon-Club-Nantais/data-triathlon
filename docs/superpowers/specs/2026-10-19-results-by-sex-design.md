# Design : filtrer et classer les résultats par sexe (epic #1643)

Sous-issues : #1644 (sondage, fait), #1645 (fiche épreuve), #1646 (`/club`),
#1647 (challenges), #1648 (`/club/athletes`). Branche d'intégration
`epic/1643-results-by-sex`, commits directs, revue sur la PR parapluie.

Sondage de référence (il prime sur ce document) :
`docs/superpowers/specs/2026-10-19-rank-gender-coverage-sondage.md`.

## Intention

Lire les résultats d'un seul sexe là où c'est utile : « le classement des
femmes sur cette épreuve », « nos podiums féminins de la saison ». Le besoin
vient d'une recette, sans demandeur identifié. On livre donc la version la plus
simple qui couvre les quatre vues, sans aller plus loin.

## Objectifs

- Un contrôle **Tous** (défaut) / **Hommes** / **Femmes** sur la fiche épreuve,
  `/club`, la fiche challenge et `/club/athletes`.
- Sur la fiche épreuve et le challenge, sous H ou F : une **place par sexe**
  fiable et un ordre qui la suit.
- Le filtre se partage par l'URL (`?sexe=H|F`), comme `?category=`.

## Non-objectifs

- `/mon-espace`, fiche athlète, `/resultats`, accueil (hors périmètre de l'epic).
- Recalcul ou correction du `rank_gender` stocké.
- Filtre par sexe sur `/courses/{id}/summary` (il reste sans paramètre, cf.
  `backend/app/api/AGENTS.md`).

## Anti-objectifs

- Afficher dans une même liste un mélange de places officielles et de places
  recalculées (le sondage montre jusqu'à 70 % de désaccord entre les deux).
- Changer quoi que ce soit au comportement par défaut d'un endpoint publié
  (Principe IV) : sans `gender`, chaque réponse reste identique octet pour octet.
- Laisser croire qu'un classement est complet quand des lignes sans sexe en
  sont exclues.

## Règles communes

- **URL** : `?sexe=H|F` ; absent ou autre valeur = Tous. Constante `SEXE_PARAM`
  et mapper `genderFromSexeParam("H"|"F") -> "M"|"F"|undefined` dans
  `frontend/lib/scope.ts`, sur le patron de `federalOnlyFromParam`.
- **API** : paramètre optionnel `gender: Literal["M","F"] | None = None` ;
  toute autre valeur → 422 (règle API). Le filtre porte sur `Athlete.gender`.
- **Lignes sans sexe** (`""`, relais mixtes compris) : exclues sous H ou F. Les
  vues de **classement** (fiche épreuve, challenge) l'écrivent quand N > 0 :
  « N résultats sans sexe connu non comptés ». *Mon choix* : pas de mention sur
  `/club` ni `/club/athletes`, qui sont des agrégats ou des listes, pas des
  classements ; cela évite un compteur de plus dans `/stats`.
- **Contrôle** : `SegmentedControl` du kit `tcn/`, options Tous / Hommes /
  Femmes, enveloppé dans `role="group"` + `aria-label="Sexe"`, cibles 44 px.
  Changer d'option remet la pagination à la page 1 (comme les autres filtres).

## Place par sexe (décision utilisateur, 19/10/2026)

Pour une épreuve et un sexe donnés :

- si **tous** les finishers de ce sexe ont un `rank_gender`, la place affichée
  est le `rank_gender` officiel, trous compris (1, 2, 3, 5…) ; c'est ce que les
  membres retrouvent sur le site du chronométreur ;
- sinon, la place est **recalculée pour toute l'épreuve** : rang parmi tous les
  finishers de ce sexe, dans l'ordre d'affichage actuel (`_display_order`), et
  l'écran le signale par un libellé discret « place recalculée ».

**Population classée** (*mon choix*) : finishers non relais, non en attente de
validation, avec un `rank_overall`. C'est elle seule qui sert au test « tous ont
un `rank_gender` » et au recalcul : une saisie manuelle validée ou un relais ne
fait donc jamais basculer une épreuve en « place recalculée ». Les autres lignes
du sexe (relais, lignes en attente, finishers sans `rank_overall`,
non-finishers) restent listées après les lignes classées, dans l'ordre actuel,
avec `gender_place = null`.

La décision se prend par (épreuve, sexe), jamais ligne à ligne. Le calcul se
fait **côté serveur**, sur l'ensemble des finishers du sexe, **avant** les
filtres `q`, `scope`/`club` et `category` : sous « TCN + Femmes », une
adhérente arrivée 12e femme affiche 12, pas 1. Les non-finishers du sexe
restent listés après les finishers, sans place.

## Par vue

### #1645 Fiche épreuve `/courses/[id]`

- `GET /courses/{id}` : nouveau paramètre `gender`. Le filtre s'ajoute dans
  `_course_rows` (qui joint déjà `Athlete`), pour `list_page_for_course` comme
  pour `list_pending_for_course`.
- Sous `gender`, l'ordre devient la place par sexe, puis les non-finishers dans
  l'ordre actuel.
- `ParticipationOut` reçoit deux champs additifs, `null` hors filtre :
  `gender_place: int | None` (place définie ci-dessus) et
  `gender_place_official: bool | None`. Sans `gender`, ils valent `null` et
  rien d'autre ne change.
- Front : `page.tsx` lit `SEXE_PARAM` et le passe à `getCourse` ; dans
  `RaceFinishers`, un second `SegmentedControl` à côté de « Tous / TCN ». Sous
  H ou F, la colonne de place affiche `gender_place`, avec « place
  recalculée » quand `gender_place_official` est faux.
- Le compte des lignes sans sexe vient du résumé déjà chargé : finishers moins
  `male` moins `female`, si `CourseSummary` compte la même population ; sinon
  le constructeur ajoute un compteur additif à la réponse de `GET /courses/{id}`.

### #1646 `/club`

- `gender` optionnel sur `GET /stats`, `GET /club/summary`, `GET /club/podiums`
  et `GET /club/best-times` (ou le nom réel de la route), propagé jusqu'aux
  requêtes des repositories (`stats_rank_rows`, `club_podiums`, roster et
  composition).
- Sous H ou F, tout le tableau de bord ne compte que les athlètes de ce sexe :
  KPI, podiums, performances par discipline, tendance mensuelle, meilleurs
  temps, aperçu de l'effectif, carte « Derniers résultats ».
- Décision utilisateur (19/10/2026) : la carte « Derniers résultats » suit le
  filtre via un `gender` optionnel ajouté à `GET /participations` (défaut
  inchangé ; `/resultats` ne l'utilise pas).
- L'axe `?rank=` reste indépendant et purement client : « Femmes » + « rang
  sexe » = podiums féminins au classement féminin.
- Effectif et aperçu de l'effectif : *mon choix*, le filtre porte sur la source
  de sexe que la section utilise déjà (`ClubMember.gender` pour un membre de la
  liste de licences sans athlète lié, `Athlete.gender` sinon), pour qu'aucun
  licencié ne disparaisse faute d'athlète lié.
- `ClubComposition` (déjà ventilée par sexe) : *mon choix*, on la masque sous
  H ou F, une répartition à 100 % d'un seul sexe n'apprend rien.

### #1647 Challenges `/challenges/[id]`

- `ChallengeResultOut` reçoit `gender: str` et `rank_gender: int | None`
  (additifs ; le modèle porte déjà les deux).
- `GET /challenges/{id}` : paramètre `gender`, même règle de place par sexe
  que la fiche épreuve (`gender_place`, `gender_place_official`). Aujourd'hui
  100 % des résultats de challenge ont un `rank_gender`, mais la règle reste la
  même pour ne pas avoir deux comportements.
- Sous `gender`, la réponse porte un compteur additif `unknown_gender_count`
  (`null` hors filtre) pour la mention des lignes sans sexe.
- Front : la page serveur lit `SEXE_PARAM`, le contrôle s'affiche au-dessus du
  tableau ; colonne de place = `gender_place` sous filtre.

### #1648 `/club/athletes`

- `AthleteSeasonActivity` reçoit `gender: str` (additif).
- *Mon choix* : filtrage **côté client** dans `AthleteSeasonList`, à côté de
  la recherche par nom et du filtre de validation déjà présents. La liste est
  chargée en entier, sans pagination ; un paramètre API n'ajouterait rien. Le
  filtre reste piloté par `?sexe=` pour être partageable.
- Pas de place par sexe ici, c'est une liste nominative.

## Contraintes

- TDD (Principe III) : chaque paramètre et chaque champ arrive avec ses tests
  API (défaut inchangé, filtre, 422) et ses tests de composant.
- Couches : le calcul de place vit dans le repository (requête) ou le service,
  jamais dans la route.
- `validated_clause` reste dans tous les agrégats touchés.
- Docs à tenir : `backend/app/api/AGENTS.md` (nouveau paramètre `gender`),
  `frontend/AGENTS.md` si un patron d'URL y est décrit.

## Laissé au constructeur

- Requête SQL exacte de la place par sexe (fenêtre `row_number` ou sous-requête,
  tant que le résultat respecte la règle et la pagination).
- Emplacement exact du contrôle dans chaque vue et formulation du libellé
  « place recalculée », dans l'esprit des pages existantes.
- Découpage en tâches et en commits, un lot par sous-issue dans l'ordre
  #1645, #1646, #1647, #1648.
