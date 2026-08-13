# Design — résolution des rôles de split ProLiveSport (issue #280)

**Date** : 2026-08-12

**Sondage de référence** : `docs/superpowers/specs/2026-08-12-prolivesport-splits-sondage.md`
(4 événements réels, 28 courses). En cas de doute, le sondage prime sur ce
design.

## Problème

`_build_split_map(splits, race) -> dict[str, str]` construit un dict
`field → role`. Un rôle peut recevoir plusieurs champs (mesuré : `bike` reçoit
`Bike`/`BikeStart`/`BikeEnd`, `run` reçoit `Run`/`RunStart` sur l'événement
979). `_parse_athlete` itère ce dict et retient, pour chaque rôle, le premier
champ non vide dans l'ordre du dict — un ordre qui reflète l'apparition dans la
réponse API, pas une garantie sémantique. Résultat mesuré : `bike_time` et
`run_time` reçoivent un point cumulé depuis le départ (`BikeEnd`, `RunStart`)
au lieu de la durée de section (`Bike`, `Run`).

## Règle de résolution retenue

Par course, pour chacun des 5 rôles (`swim`, `t1`, `bike`, `t2`, `run`) :

- **Un seul champ candidat** → il alimente le slot positionnel correspondant
  (`swim_time`, `t1_time`, `bike_time`, `t2_time`, `run_time`), **comportement
  inchangé** par rapport à aujourd'hui pour ce rôle.
- **Zéro candidat** → le slot reste vide (déjà le comportement actuel).
- **Deux candidats ou plus, pour au moins un rôle de la course** → **aucun**
  slot positionnel n'est renseigné pour **cette course**, y compris les rôles
  par ailleurs non ambigus (swim/t1/t2 sur 979, par exemple). À la place, tous
  les champs de splits de la course (candidats ambigus, candidats non ambigus,
  et champs à libellé non classifié comme `SplitN`) partent dans
  `ScrapedResult.segments`, triés par le suffixe numérique du champ (`T3` → 3),
  avec le libellé source conservé tel quel (`Bike`, `BikeStart`, `BikeEnd`,
  `Run`, `RunStart`, `Split1`…).

### Pourquoi « tout ou rien » par course, et pas juste les rôles ambigus

`services/mapping.build_splits` a un comportement **tout-ou-rien** déjà en
place : si `ScrapedResult.segments` est renseigné, il prime **entièrement**
sur les 5 slots positionnels — ces derniers sont ignorés, pas fusionnés
(`backend/app/services/mapping.py:73-83`). Si on renseignait `bike_time`
**et** `segments` simultanément pour la même participation, `build_splits`
ignorerait silencieusement `bike_time` : le slot positionnel correctement
résolu disparaîtrait de `Participation.splits`. Pour ne rien perdre, dès
qu'une course bascule en `segments`, **tous** ses champs (y compris ceux
d'un rôle non ambigu) doivent y être portés — sans quoi `swim_time`/`t1_time`/
`t2_time`, pourtant corrects, seraient éclipsés par un `segments` incomplet.

Modifier `mapping.build_splits` pour fusionner les deux chemins est écarté :
c'est de l'infra partagée par tous les scrapers (oktime, klikego, RaceResult,
timepulse…), et aucun autre fournisseur n'a besoin d'un mélange par
participation — élargir son contrat pour un seul provider ambigu serait une
indirection spéculative (principe de conception du dépôt : pas d'abstraction
non justifiée par le besoin actuel).

### Tri des champs dans `segments`

Le suffixe numérique du champ (`T1`, `T2`, … `T11`) n'est pas garanti
chronologique en toute rigueur, mais il l'est sur tout le panel mesuré : les 5
champs canoniques (`T1..T5`) précèdent les cumulés étendus (`T6..T8`), qui
précèdent les checkpoints génériques (`T9..T11`) — une lecture « répartition
de base, puis points supplémentaires » cohérente pour l'affichage. C'est plus
lisible que l'ordre brut de la réponse API, qui est mélangé (mesuré :
`T1, T9, T8, T7, T6, T5, T4, T3, T2, T11, T10` pour 979/Triathlon M) et
produirait un affichage incompréhensible.

## Impact sur `_build_split_map`

Le type de retour change : il ne peut plus être un simple `dict[field, role]`
si on doit détecter l'ambiguïté (compter les candidats par rôle) **et**
conserver, pour le chemin `segments`, la liste ordonnée de **tous** les champs
de la course avec leur libellé source — y compris ceux sans rôle reconnu.

Forme retenue : `_build_split_map` rend une structure qui expose, par rôle,
la **liste** des champs candidats (pas un seul), plus la liste complète
`(field, label)` de la course dans l'ordre de la réponse API (pour construire
`segments` si nécessaire). Un rôle avec `len(candidats) == 1` est résolu ; à
partir de 2, il est ambigu. Signature indicative (à affiner en tâche
d'implémentation, pas figée ici) :

```python
def _build_split_map(splits: list, race: str) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    """(candidats par rôle, tous les champs (field, label) de la course, triés
    par suffixe numérique)."""
```

## Impact sur `_parse_athlete`

- Calcule si la course est « ambiguë » (au moins un rôle à ≥ 2 candidats).
- Si **non ambiguë** : comportement inchangé — pour chaque rôle à candidat
  unique, lit `time{field}`, l'affecte au slot positionnel si non vide et
  différent de `00:00:00` (règle déjà en place).
- Si **ambiguë** : ne renseigne **aucun** slot positionnel ; construit
  `result.segments` à partir de la liste complète des champs de la course
  (triée par suffixe numérique), en ne gardant que les champs dont
  `time{field}` est non vide et différent de `00:00:00` — même garde que les
  slots positionnels aujourd'hui.

## Non-régression attendue

| Événement / course | Ambiguïté détectée | Comportement |
| --- | --- | --- |
| 979, Triathlon M et S | Oui (`bike`: 3 candidats, `run`: 2 candidats) | Slots vides, `segments` = tous les champs (Swim, #1, Bike, #2, Run, BikeStart, BikeEnd, RunStart, SplitN) |
| 1082, ses 11 courses | Non (1 seul candidat par rôle canonique) | **Inchangé** — `bike_time`/`run_time`/etc. renseignés comme aujourd'hui ; `SplitN` reste hors `splits`/`segments`, toujours présent dans `raw_data` |
| 1079, ses 3 courses | Non | **Inchangé**, même raisonnement que 1082 |
| 1060, ses 11 courses | Non (aucun candidat, libellés `SportN` non reconnus) | **Inchangé** — slots déjà vides aujourd'hui, `raw_data` conserve les valeurs brutes |

Aucune des 26 courses déjà correctes n'est affectée. Seules les 2 courses de
979 changent de représentation (slots vides → `segments` complet), ce qui est
l'objet même du correctif.

## Test de non-régression exigé par l'issue

Sur la carte de l'événement 979 (`{T1: swim, T2: t1, T3: bike, T6: bike,
T7: bike, T4: t2, T5: run, T8: run}`, telle que citée par l'issue) : vérifier
que `bike` et `run` sont détectés ambigus (candidats `{T3, T6, T7}` et
`{T5, T8}` respectivement), que `bike_time` et `run_time` du `ScrapedResult`
résultant sont vides, et que `segments` contient les 8 entrées (labels sources
Swim/T1.../Bike/BikeStart/BikeEnd/#2/Run/RunStart — libellés exacts à vérifier
contre la fixture) avec leurs temps. Un test complémentaire vérifie la
non-régression sur une course à candidat unique (1082-like : un seul champ par
rôle) : slots positionnels renseignés, `segments` vide.

## Mise à jour de `docs/scrapers/prolivesport.md`

La section « Défaut connu, hors périmètre (#280) » est remplacée par une
section décrivant le **comportement retenu** (pas le défaut) : la règle
« un candidat par rôle → slot positionnel ; ≥ 2 candidats pour un rôle de la
course → toute la course part dans `segments` », avec référence au sondage et
à ce design. Le renvoi vers #280 dans le sondage #269 et dans
`backend/app/scrapers/AGENTS.md` (tableau des fournisseurs) reste correct
tel quel (il pointe vers l'issue, qui se ferme avec ce correctif) et n'a pas
besoin d'édition séparée.

## Hors périmètre (confirmé par le sondage)

- Reconnaissance de libellés génériques isolés (`SportN` sur le duathlon 1060,
  `SplitN` sur 1082/1079 quand aucune ambiguïté ne force le basculement en
  `segments`) : aucun indice fiable dans le libellé pour les rattacher à un
  sport, deviner romprait le principe de simplicité. Ces valeurs restent
  accessibles via `raw_data`, ce qui satisfait le critère d'acceptation « pas
  perdus (segments ou raw_data) » sans changement de code.
- Dérivation par différence de cumulés (piste 2) : écartée, cf. sondage
  constat n° 5.

## Révision (13/08/2026) — après revue humaine du rendu frontend

La règle initiale (« ambiguïté ⇒ toute la course part dans `segments` ») a
produit, sur les 2 courses ambiguës de 979, un tableau de résultats à
14 colonnes (les 5 rôles canoniques **et** `BikeStart`/`BikeEnd`/`RunStart`/
`Split1..3`) — non anticipé lors du design, faute d'avoir vérifié le rendu
frontend avant la sortie de draft. Le test manuel demandé par la PR l'a
débusqué.

Le sondage donnait pourtant déjà de quoi trancher (constat n°3) : un champ
dont le libellé finit par `start`/`end` est un point cumulé depuis le départ,
jamais une durée de section. Exclure ces champs de la candidature d'un rôle
laisse `Bike`/`Run` seuls candidats sur 979 — bike/run se résolvent donc
normalement, sans jamais passer par `segments` pour ce panel. Le repli
`segments` reste en place pour une ambiguïté qui résisterait à cette
exclusion (deux candidats non cumulés pour un même rôle), non mesurée à ce
jour. Aucun re-sondage n'était nécessaire : la donnée était déjà là, seule
l'arbitrage a changé.
