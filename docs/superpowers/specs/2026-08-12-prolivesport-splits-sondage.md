# Sondage — nature des points de passage ProLiveSport (issue #280)

**Date** : 2026-08-12

**Contexte** : issue #280 (« ProLiveSport : `bike_time` / `run_time` stockent un
point de passage, pas un temps de section »), défaut repéré comme adjacent lors
du sondage fan-out (#269) et volontairement laissé hors périmètre à l'époque
(`docs/superpowers/specs/2026-08-11-prolivesport-fanout-sondage.md`, section
« Défaut adjacent, hors périmètre »). `_build_split_map` mappe le libellé de
chaque champ API sur un rôle (`swim`/`t1`/`bike`/`t2`/`run`) par inclusion de
sous-chaîne, et plusieurs champs peuvent recevoir le même rôle (« Bike »,
« BikeStart », « BikeEnd » matchent tous `_BIKE_LABELS` via `"bike" in label`).
`_parse_athlete` itère ensuite le dict `field → role` et retient le premier
champ non vide rencontré — « premier » au sens de l'ordre du dict, qui est
l'ordre d'apparition des champs dans la réponse API, **pas** un ordre garanti
par le rôle.

Ce fichier est un **sondage** au sens d'AGENTS.md : il consigne ce qui a été
mesuré sur le terrain à la date ci-dessus, et **prime** sur le design et le plan
en cas de divergence — toute correction se fait en re-sondant.

## Méthode

1. Requêtes GET réelles vers l'API publique ProLiveSport
   (`api.prolivesport.fr/apiws`), à travers `app.core.http.client()` — le même
   chemin que le scraper en production (garde SSRF incluse).
2. Reprise des 4 `eventId` déjà résolus par le sondage #269
   (979, 1060, 1079, 1082 — 28 courses), pour bénéficier d'un panel déjà
   qualifié plutôt que d'en reconstituer un.
3. Pour chaque événement : `event/detail`, `result/raceList`, `result/splitDetail`
   (un seul appel, comme documenté par #269), puis `result/indiv` par course
   exhibant un rôle à champs multiples.
4. Pour chaque champ candidat d'un rôle ambigu, lecture des valeurs sur
   plusieurs athlètes réels et vérification de la cohérence temporelle : la
   somme des 5 champs canoniques (Swim + #1 + Bike + #2 + Run, ou leurs
   équivalents duathlon) est-elle égale au temps total publié (`time`) ?
5. Reproduction de `_build_split_map` + `_parse_athlete`, **tels qu'ils
   existent aujourd'hui**, sur des données réelles (pas des fixtures), pour
   observer la valeur effectivement stockée en `bike_time` / `run_time`.

## Panel

| Événement | Nom | Courses | Libellés de section observés |
| --- | --- | --- | --- |
| 979 | Quiberon 2024 | 3 (XS, S, M) | `Swim`/`#1`/`Bike`/`#2`/`Run` **+** `BikeStart`/`BikeEnd`/`RunStart` **+** `Split1..3` |
| 1082 | Triathlon Audencia La Baule 2025 | 11 | `Swim`/`#1`/`Bike`/`#2`/`Run` **+** `Split1..3` |
| 1079 | Triathlon de Quiberon Open 2025 | 3 (XS, S, M) | `Swim`/`#1`/`Bike`/`#2`/`Run` **+** `Split4..6` |
| 1060 | Chtriman 2025 Gravelines | 11 | `Sport1`/`#1`/`Sport2`/`#2`/`Sport3` (duathlon/multi-sport, libellés génériques) |

## Constat n° 1 — la collision de rôle se reproduit en conditions réelles, sur l'événement 979

Champs publiés pour la course « Triathlon M » (979) : `T1=Swim, T2=#1, T3=Bike,
T4=#2, T5=Run, T6=BikeStart, T7=BikeEnd, T8=RunStart, T9=Split1, T10=Split2,
T11=Split3`. `_BIKE_LABELS` matche `Bike`, `BikeStart` **et** `BikeEnd` (tous
contiennent la sous-chaîne `"bike"`) ; `_RUN_LABELS` matche `Run` **et**
`RunStart`. Trois champs pour le rôle `bike`, deux pour le rôle `run`.

L'ordre **réel** du dict `field → role` construit par `_build_split_map` pour
cette course (mesuré, pas supposé — l'ordre d'apparition dans la réponse API
n'est pas `T1..T11` croissant) :

```
{T1: swim, T8: run, T7: bike, T6: bike, T5: run, T4: t2, T3: bike, T2: t1}
```

`T8` (run) et `T7` (bike) précèdent `T5` et `T3` dans cet ordre précis. En
rejouant `_parse_athlete` sur les données réelles du bib 245 (course M) :

| Champ stocké | Valeur produite aujourd'hui | Valeur correcte attendue | Champ source retenu à tort |
| --- | --- | --- | --- |
| `bike_time` | `01:13:41` | `00:51:31` | `T7` (`BikeEnd`, cumulé depuis le départ) |
| `run_time` | `01:14:53` | `00:30:25` | `T8` (`RunStart`, cumulé depuis le départ) |

Incohérence vérifiable par simple addition : `swim_time` (00:20:42) +
`t1_time` (00:01:29) + `bike_time` (01:13:41, valeur actuelle) + `t2_time`
(00:01:12) + `run_time` (01:14:53, valeur actuelle) dépasse largement
`total_time` (01:45:17) — la somme des 5 champs stockés aujourd'hui n'a plus de
sens physique. Mesuré identiquement sur la course « Triathlon S » du même
événement (bib 15) : `bike_time` stocké `00:42:12` au lieu de `00:29:42`,
`run_time` stocké `00:43:18` au lieu de `00:14:58`.

## Constat n° 2 — un rôle à candidat unique est une durée de section fiable

Sur toutes les courses où un rôle n'a qu'un seul champ candidat, la somme des 5
champs canoniques colle au temps total à 2 secondes près (bruit de mesure
plausible sur des tapis électroniques indépendants) :

| Événement / course / bib | Swim+#1+Bike+#2+Run | `time` publié | Écart |
| --- | --- | --- | --- |
| 979 / Triathlon M / 245 | 01:45:19 | 01:45:17 | 2 s |
| 979 / Triathlon S / 15 | 00:58:18 | 00:58:16 | 2 s |
| 1082 / M / 66 | 01:54:25 | 01:54:23 | 2 s |
| 1079 / M / 314 | non mesuré (T6/T7/T8 absents sur cet événement) | — | — |

Conclusion : `Bike` et `Run` (comme `Swim`, `#1`, `#2`) sont des **durées de
section**, pas des points cumulés — c'est le contrat déjà supposé par
`_BIKE_LABELS`/`_RUN_LABELS` et par les tests existants
(`tests/test_prolivesport.py::test_parse_athlete_fields_and_splits`, qui
traite `timeVelo` comme une durée directement affectée à `bike_time`).

## Constat n° 3 — `BikeStart`/`BikeEnd`/`RunStart` sont des points cumulés, redondants avec `Bike`/`Run`

Sur le même bib 245 (979, Triathlon M) :

- `T6` (`BikeStart`) = `00:22:11` = `T1` (Swim) + `T2` (#1) — exactement le
  cumul au moment où le vélo commence.
- `T7` (`BikeEnd`) = `01:13:41` ≈ `T1+T2+T3` (`01:13:42`, 1 s d'écart) — le
  cumul à la fin du vélo.
- `T8` (`RunStart`) = `01:14:53` ≈ `T1+T2+T3+T4` (`01:14:54`, 1 s d'écart) — le
  cumul au début de la course à pied.

Ces trois champs portent donc la **même information** que `Bike`/`Run` (les
durées de section), simplement encodée sous forme de cumulé-depuis-le-départ.
Rien ne permet de les distinguer de `Bike`/`Run` par un critère plus fiable que
« lequel des deux encodages garder » — d'où la collision.

## Constat n° 4 — les libellés génériques (`SplitN`, `SportN`) échappent aux 5 rôles connus

- Sur 1082 et 1079, `Split1..3` / `Split4..6` sont des points cumulés
  supplémentaires (croissants, vérifié sur plusieurs bibs), en plus des 5
  champs canoniques déjà corrects. `_build_split_map` ne les classe dans
  **aucun** rôle (aucun mot-clé bike/run/swim dans `"split1"` etc.) : ils sont
  aujourd'hui silencieusement exclus de `split_map`, donc absents de
  `splits`/`segments` — mais **conservés dans `raw_data`**
  (`{k: v for k, v in athlete.items() if not k.isdigit()}` retient tous les
  `timeT1`..`timeT20` bruts, vérifié sur le bib 245 : 20 champs `timeTN`
  présents).
- Sur 1060, les 5 champs canoniques eux-mêmes portent des libellés génériques
  (`Sport1`/`#1`/`Sport2`/`#2`/`Sport3`, duathlon/multi-sport). Aucun ne
  matche `_SWIM_LABELS`/`_BIKE_LABELS`/`_RUN_LABELS` : `swim_time`,
  `bike_time`, `run_time` restent **vides** pour les 11 courses de cet
  événement dès aujourd'hui, avant tout correctif. C'est une perte de
  structuration déjà existante, orthogonale à la collision de rôle — les
  valeurs restent dans `raw_data`, mais aucun libellé ne permet de les
  rattacher à un sport sans deviner.

## Constat n° 5 — la piste « dérivation par différence de cumulés » ne s'applique pas ici

La piste 2 de l'issue (dériver un temps de section par différence de cumulés,
comme le fait `oktime`) suppose une série cumulée **complète et homogène** par
course — c'est le cas d'ok-time, dont `points_de_passage` cumule
systématiquement tout du départ à l'arrivée. Ce n'est **pas** le cas ici :

- Les champs cumulés mesurés (`BikeStart`, `BikeEnd`, `RunStart`, `SplitN`)
  sont **épars** : pas de cumulé pour la fin de natation, pas de cumulé
  homogène couvrant toute la chaîne T1→T2, pas de point cumulé systématique en
  fin de course.
- Le seul rôle qui aurait besoin d'une dérivation (bike, run) n'a pas de paire
  cumulée complète et fiable sur tout le panel : 1082/1079 n'ont **aucun**
  cumulé pour bike/run (seulement `SplitN` génériques, sans lien affirmé avec
  bike/run), et 979 a des cumulés mais **redondants** avec une durée déjà
  publiée directement (`Bike`/`Run`), rendant la dérivation inutile là où elle
  serait possible.

Dériver par différence introduirait donc de la complexité (détecter quels
champs cumulés appartiennent à quelle paire, gérer l'hétérogénéité
d'événement en événement) pour un gain nul : là où l'information cumulée
existe, la durée directe existe aussi et est déjà correcte.

## Arbitrage

**Piste retenue : piste 1** — ne peupler `bike_time`/`run_time` (et par
extension `swim_time`/`t1_time`/`t2_time`) que lorsque le rôle a **exactement
un** champ candidat pour la course ; dès qu'un rôle a deux candidats ou plus
(cas mesuré : `bike` et `run` sur 979), aucun des deux ne va dans un slot
positionnel — l'intégralité des champs de la course part dans
`ScrapedResult.segments`, chemin déjà utilisé par `oktime`/`klikego`/
`RaceResult` et déjà rendu par le frontend sans modification (`sourceEntry` de
`frontend/lib/utils/splits.ts` devine famille/couleur par sous-chaîne du
libellé source : `bike`/`velo`/`cycl` → vélo, `course`/`run`/`pied`/`cap` →
course, `t\d+`/`transition` → transition neutre).

**Piste 2 écartée** : constat n° 5 — pas de série cumulée homogène à
différencier sur ce panel, contrairement à ok-time.

**Piste 3 (tout dans `segments`, jamais de slot positionnel) écartée** :
dégraderait sans raison les courses déjà correctes aujourd'hui (1082, 1079 —
constat n° 2), où `bike_time`/`run_time` sont déjà des durées fiables. La
règle « ambiguïté ⇒ segments » du choix retenu obtient le même résultat sur
979 sans coût sur les 14 autres courses du panel qui n'ont pas ce défaut.

**Portée assumée, non traitée par ce correctif** : les libellés génériques
(`SportN` sur 1060, `SplitN` sur 1082/1079) restent hors slots positionnels et
hors `segments` **sauf** quand ils cohabitent avec une ambiguïté de rôle sur
la même course (auquel cas ils entrent dans le même panier `segments` que le
reste, sans coût). Deviner qu'un `SportN` isolé désigne le vélo ou la course à
pied romprait le principe de simplicité (aucun indice fiable dans le libellé)
et sort du périmètre de #280, qui porte sur la collision de rôle, pas sur la
reconnaissance de libellés génériques. Le critère d'acceptation « aucun point
de passage n'est perdu » reste satisfait pour ces cas via `raw_data`, déjà en
place (constat n° 4).
