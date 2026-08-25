# Bande personnelle « Ma saison » en tête du tableau de bord — design (NAV-9)

**Issue** : [#502](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/502) (epic #460, audit #325)
**Date** : 2026-08-25
**Statut** : en design

## Le problème

`NAV-9` du § 10 de l'audit UI/UX
(`docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`), cluster « à quoi
sert un athlète retenu ? », question versée par #323.

L'écran d'atterrissage — `/dashboard`, où `/` redirige — ne parle que du club en
agrégat. Le membre qui a désigné son nom n'y trouve **rien de lui**. Le stock
`tcn-athlete` n'a jusqu'ici que trois consommateurs, tous sur le geste de choix
lui-même (`AppNav`, `AthleteSelection`, `AthleteAvatar`) : aucun écran ne filtre,
ne trie, ni ne se personnalise dessus. La boucle se referme sur elle-même — rien
ne motive le geste, donc personne ne le fait, donc personne ne réclame la
personnalisation.

Corollaire relevé par le même § 10 : l'objet porte **quatre noms** selon
l'endroit, et la promesse n'est énoncée nulle part.

Dépendance bloquante levée : **#467** (`PROF-7`) est fermée depuis le
2026-08-22.

## Ce qui était déjà tranché, et n'est pas rejugé ici

**Le transport.** `frontend/AGENTS.md:218-245` porte l'arbitrage du cluster,
posé par #467 et déclaré valable pour #502, #503 et #504 : l'athlète retenu vit
en `localStorage`, **ne franchit pas la frontière serveur**, et **aucun cookie
miroir** n'en est fait. Trois raisons y sont écrites — aucun rendu serveur n'en
a besoin, le coût de cache est réel sur les pages en revalidation courte
(#352), et un miroir c'est deux stocks à tenir synchronisés. La bande est donc
un bloc **client** monté sous un `/dashboard` qui reste rendu serveur.

Ce design ne rouvre pas non plus l'identité visuelle (`--tcn-*`, Anton/Barlow)
ni la frontière `components/tcn/` vs `components/ui/` — contraintes de #325,
rappelées par #460.

## Décisions de cadrage

| Question | Décision |
| --- | --- |
| Que porte la bande | L'exemple strict de l'audit : **épreuves** et **podiums**, mis en regard du club. Pas les cinq indicateurs du profil — trois d'entre eux (meilleure place, meilleur ratio, format favori) n'ont **aucun** homologue dans `Stats`, la bande mêlerait alors comparaison et record de carrière |
| Où va le chiffre du club | Sur les **épreuves seules**, comme l'exemple de l'audit. Le compteur de podiums du club est déjà à l'écran, dans les `StatCardsRank` juste dessous — le répéter dans la bande ferait deux fois le même chiffre à trente pixels d'écart |
| Filtres suivis | Les **trois** : saisons, disciplines (`?sports`) et type de rang (`?rank`). C'est précisément parce que le podium du club se lit dans les cartes du dessous que le mien doit se calculer sur le même rang : « 1 podium » scratch au-dessus de « 11 podiums » catégorie induirait en erreur dès la première bascule du toggle |
| D'où viennent mes chiffres | `GET /athletes/{id}` gagne `seasons` et `federal_only`, **optionnels et sans effet par défaut**. La règle fédérale reste dans `app/core/discipline.py` |
| Pourquoi pas une recopie front de `NON_FEDERAL_TYPES` | Dupliquer une règle métier que la codebase garde délibérément côté serveur — le front « n'a plus d'opinion » (cf. `lib/scope.ts`, #76). Deux listes à tenir synchronisées, dont une qui se périmerait en silence |
| Pourquoi pas une route de résumé dédiée | Une surface d'API de plus pour deux entiers, et le calcul de rang se dédoublerait backend/front alors qu'il doit rester le miroir de `_accumule` |
| Unité de « mes épreuves » | `course_id` **distincts**, pas le nombre de participations — parité exacte avec `stats.events`, qui compte des courses distinctes. Un athlète inscrit en solo *et* en relais sur la même course y compterait sinon pour deux |
| Résultats en attente de validation | Exclus (`!is_pending_validation`), même règle que les cinq `StatCard` du profil et que `for_stats` côté club (#270, FR-021) |
| Quand la bande s'affiche | Branche non-vide de `/dashboard` seulement : si `stats.total === 0`, ma saison l'est par construction et l'`EmptyState` du club porte déjà la sortie |
| Décalage à l'hydratation | Assumé — c'est le prix déjà payé par #467. Réduit à **un seul** décalage : le squelette monte dès l'hydratation à la hauteur définitive, pas un second au retour du fetch |
| Échec du fetch | La bande reste, avec le nom et le lien ; les chiffres deviennent « — » et une mention « chiffres indisponibles ». Pas de disparition silencieuse : le membre a vu la bande, elle ne doit pas s'évaporer |
| Nom unique de l'objet | « **Mon athlète** ». Les verbes restent distincts (« Choisir cet athlète », « Sélectionnez votre nom ») : ce sont des actions, pas le nom de l'objet |
| Forme d'adresse | Vouvoiement, conformément à #478 — d'où « Votre tableau de bord affichera vos résultats en premier », et non le tutoiement du texte de l'issue |

## Contrat de données — backend

`GET /athletes/{athlete_id}` (`backend/app/api/v1/athletes.py:78`) gagne deux
paramètres de requête :

```python
@router.get("/athletes/{athlete_id}")
def get_athlete(
    athlete_id: int,
    seasons: str | None = Query(None),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
```

Ils descendent dans `participation_repository.list_for_athlete`, qui applique
les mêmes clauses que `for_stats` :

```python
def list_for_athlete(
    db: Session,
    athlete_id: int,
    *,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[Participation]:
```

`seasons` se parse par `app.core.season.parse_seasons`, comme partout ailleurs.
Le `join(Course, ...)` ne s'ajoute que si l'un des deux filtres est demandé —
même forme que `for_stats:594-599`.

**Additif, donc conforme au Principe IV.** Les défauts (`None` / `False`)
reproduisent le comportement d'aujourd'hui au caractère près : `/athletes/[id]`,
qui appelle par `apiServer.getAthlete(id)` sans filtre, ne bouge pas. Les cinq
`StatCard` du profil et les filtres en mémoire d'`EventsTable` (#489) restent
calculés sur l'ensemble d'une carrière, comme le veut leur carte « Toutes les
épreuves ».

`finishers_count_by_group` continue de porter sur les seules participations
rendues — la liste filtrée, donc, ce qui réduit aussi son travail.

## Le calcul — côté client

Nouveau `apiClient.getAthlete(id, filters)` dans `lib/api/client.ts` : le client
n'a aujourd'hui que `apiServer.getAthlete`, la route n'ayant jamais été
appelée depuis le navigateur.

Sur la réponse, la bande calcule deux entiers dans une fonction pure et testable
(`lib/utils/ma-saison.ts`) :

- **épreuves** — cardinal de `new Set(validated.map((p) => p.course.id))` ;
- **podiums** — nombre de participations dont le rang est `<= 3` sur le champ
  que désigne `?rank=` :

| `?rank=` | Champ lu | Miroir backend |
| --- | --- | --- |
| `scratch` (défaut) | `rank_overall` | `_accumule(scratch, p.rank_overall)` |
| `category` | `rank_category` | `_accumule(category, p.rank_category)` |
| `gender` | `rank_gender` | `_accumule(genre[…], p.rank_gender)` |
| `all` | le **meilleur** des trois | `_accumule(tous, _meilleur_rang([...]))` |

C'est la reprise littérale de `stats_service._rank_counters` — un rang `None` ou
`< 1` ne compte pas, la borne est `<= 3`. Le tableau ci-dessus est le contrat à
tester ; toute divergence rendrait la mise en regard fausse sans qu'elle se
voie.

**Le mode `gender` ne se ventile pas ici.** Le club l'affiche en paire F/H parce
qu'il agrège des centaines d'athlètes ; un athlète a un seul sexe, et son
compteur est simplement celui de son propre `rank_gender`. La comparaison porte
alors sur le total F+H du club, comme le fait déjà `texteAnnonce` dans
`StatCardsRank`.

## Le composant

`components/dashboard/MaSaison.tsx`, client.

**Lecture du stock.** Nouveau hook `useSelectedAthlete()` à côté de
`useIsSelectedAthlete` dans `components/layout/AthletePicker.tsx` — même
`useSyncExternalStore`, même abonnement à `ATHLETE_CHANGED_EVENT`, instantané
serveur `null`. `getSnapshot` doit rendre une valeur **stable** d'un appel à
l'autre, or `readAthlete()` reconstruit un objet à chaque lecture : le hook
mémoïse donc sur la chaîne brute du `localStorage`, et ne reconstruit l'objet
que lorsqu'elle change. C'est exactement la raison pour laquelle
`useIsSelectedAthlete` rend un booléen et non l'athlète (commentaire
`AthletePicker.tsx:91-93`) — le nouveau hook lève la contrainte au lieu de la
contourner.

**Fetch.** `useEffect` clé sur `(id, seasons, federal_only)`, annulé au
démontage et à tout changement de clé. `?rank` **ne** déclenche **pas** de
fetch : il ne change que la lecture d'un champ déjà en main — même arbitrage que
`RankTypeToggle` (#328) et qu'`EventsTable` (#489).

**Rendu.**

```
MA SAISON
Jean Dupont — 4 épreuves · 1 podium au scratch          Voir mon athlète →
Le club a couru 32 épreuves sur la même sélection.
```

Quatre états :

| État | Rendu |
| --- | --- |
| Aucun athlète retenu | Rien. **Pas de place réservée** — ce serait une bande vide pour l'écrasante majorité des visiteurs |
| Chargement | Squelette à la **hauteur définitive** de la bande remplie (`components/ui/skeleton`, cf. #476) |
| Saison vide | « Jean Dupont — aucune épreuve sur cette sélection. » + « Le club en a couru 32. » + sortie « Ajouter un résultat → » |
| Échec du fetch | Nom et lien conservés, chiffres en « — », mention « chiffres indisponibles » |

Pluriels : réemploi de la forme `motCompte` de `StatCardsRank` — « 1 podium » /
« 2 podiums », « 1 épreuve » / « 4 épreuves ». À extraire dans
`lib/utils/format.ts` plutôt qu'à recopier, puisqu'elle sert désormais deux
appelants.

## Insertion dans `/dashboard`

Dans `app/(public_restricted)/dashboard/page.tsx`, au-dessus de la grille de
`StatCard`, à l'intérieur de la branche non-vide :

```tsx
<MaSaison
  clubEvents={stats.events}
  clubRankCounters={stats.rank_counters}
  seasons={selected}
  federalOnly={federal_only}
/>
```

Les quatre props sont sérialisables — le serveur ne passe que des nombres, des
objets simples et un tableau d'années. La page reste un composant serveur.

**Annonce (#477).** `AnnonceStatut` sur changement de saison, de discipline ou
de rang, comme `StatCardsRank` : le toggle de rang écrit l'URL par
`history.pushState` (#328), donc rien ne navigue et rien ne recharge — sans
annonce, la bascule est muette pour un lecteur d'écran. Pas d'annonce à la
**première** apparition, qui serait du bruit à chaque chargement de page.

## Microcopie — un seul nom pour l'objet

| Où | Aujourd'hui | Après |
| --- | --- | --- |
| `AthletePicker.tsx` — eyebrow de la modale | « Accès athlète » | « Mon athlète » |
| `AthletePicker.tsx` — pied de modale | « Pas de blocage d'accès — choisissez librement votre profil. » | « Votre tableau de bord affichera vos résultats en premier. » |
| `AppNav.tsx` — tuile du rail (`aria-label`, tooltip) | « Mon profil » | « Mon athlète » |
| `AthleteSelection.tsx` — bénéfice sous le bouton | « …retrouver ses résultats en un geste et se comparer au club » | « …retrouver ses résultats en un geste et voir sa saison en tête du tableau de bord » |

Ne bougent pas : le titre de la modale (« Sélectionnez votre nom ») et les
libellés de bouton (« Choisir cet athlète », « Ne plus choisir cet athlète »).
Ce sont des **actions** — le § 10 reproche quatre noms de l'objet, pas quatre
verbes ; et l'unification des verbes a déjà été faite par #323 puis #478.

Le pied de modale change de nature : d'un rassurant sans contenu (« pas de
blocage d'accès » répond à une inquiétude que personne n'a exprimée) à la
promesse que la bande tient désormais réellement. C'est le point du gradient de
but cité par l'audit — un dispositif ne se maintient que si le progrès qu'il
apporte est visible.

## Tests

Le TDD est non négociable (Principe III). Chaque comportement ci-dessous a son
test **avant** son implémentation.

**Backend** (`pytest -m "not integration"`) :

- `GET /athletes/{id}` sans paramètre rend exactement ce qu'il rendait — la
  non-régression du contrat publié ;
- `?seasons=2025` ne rend que les participations de cette saison ;
- `?federal_only=true` retire trail, course à pied et cyclisme ;
- les deux combinés ;
- `?seasons=` vide ou non parsable retombe sur « toutes », comme
  `parse_seasons` le fait partout ailleurs.

**Frontend** (`vitest`) :

- la fonction pure de comptage — les quatre modes de rang face à un jeu de
  participations couvrant `None`, `0`, `3` et `4` sur chaque champ ; le cardinal
  distinct sur un athlète solo + relais d'une même course ; l'exclusion des
  `is_pending_validation` ;
- `useSelectedAthlete` — `null` au rendu serveur, l'athlète après hydratation,
  resynchronisation sur `ATHLETE_CHANGED_EVENT`, **stabilité de l'instantané**
  (deux lectures successives sans écriture rendent la même référence, sinon
  `useSyncExternalStore` boucle) ;
- `MaSaison` — les quatre états ; aucun fetch quand aucun athlète n'est retenu ;
  un fetch quand `seasons` ou `federalOnly` change ; **aucun** fetch quand
  `?rank` change, mais un recalcul du podium ;
- la microcopie — les quatre libellés, dans leurs fichiers respectifs.

## Hors périmètre

- `NAV-10` (#503) et `PROF-8` (#504), les deux autres lots du cluster : ils
  héritent de l'arbitrage de transport, pas de ce composant.
- Les alertes et notifications, et la personnalisation de `/benevoles` —
  écartées par le § 10 lui-même, pour des raisons qui n'ont pas bougé.
- Toute reprise des cinq `StatCard` du profil : elles restent les records d'une
  carrière, la bande est une lecture de saison.
