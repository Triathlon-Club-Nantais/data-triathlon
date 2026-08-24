# Rafraîchir les participations au ré-import (upsert)

**Date** : 2026-07-14
**Statut** : implémenté (#68) — voir le plan `docs/superpowers/plans/2026-07-24-upsert-participations-rescrape.md`

## Problème

`rescrape-db` ne rafraîchit aucune donnée. Sur une base déjà peuplée, son bilan
est invariablement :

```
Épreuves ciblées          : 42
Participants ajoutés      : 0
Participants déjà en base : 5820
```

Le scraping HTTP a bien lieu — `force=True` court-circuite le cache TTL — et les
5820 participants sont bien re-téléchargés. Mais à la persistance,
`import_service._Persister.add` jette la ligne fraîche dès que le dossard existe
sur la course :

```python
if bib in bibs:
    self.skipped += 1
    return
```

Il n'existe d'ailleurs aucune fonction `update` dans `participation_repository` :
le persister est en **insertion seule**. Un temps corrigé par le chronométreur,
un classement recalculé, un split ajouté après coup : rien de tout cela n'entre
jamais en base. Les seuls effets réels d'un rescrape aujourd'hui sont de mettre à
jour `scraped_at`, recalculer l'indice de fiabilité, et insérer les participants
véritablement nouveaux.

**La même faille casse la course en direct.** `cache.is_fresh` retient un TTL de
10 minutes tant qu'une participation n'a pas de `total_time` — un TTL court dont
la raison d'être est justement de rafraîchir une épreuve en cours. Ce TTL expire,
l'import web re-scrape… et le persister jette tout. Le TTL court est aujourd'hui
sans effet : une course suivie en direct ne voit jamais ses temps se mettre à
jour, ni en CLI ni dans l'UI.

## Décisions

| Question | Décision |
| --- | --- |
| Périmètre | **Tout import** : rescrape-db, import-sheet et import web (SSE). Une seule sémantique de persistance. |
| Écrasement | **Prudent** : une valeur vide venue de la source ne remplace jamais une valeur déjà en base. |
| Sans dossard | **MAJ si non ambigu** : un seul exemplaire de l'athlète sur la course → mise à jour ; plusieurs → skip, comme aujourd'hui. |
| Compteurs | Compteur **`updated`** dédié, propagé jusqu'au front. |

## Conception

### 1. Le persister devient un upsert

`_Persister.add` reste le **seul** point de persistance d'une participation, pour
les trois entrées. Il cesse d'être en insertion seule.

Aujourd'hui il ne charge que les *dossards* existants
(`participation_repository.existing_bibs_for_course` → `set[str]`). Pour mettre à
jour, il lui faut les lignes elles-mêmes : il charge donc les `Participation` de
la course (une requête par course, comme aujourd'hui) et les indexe par dossard.

`participation_repository` gagne un `update(db, participation, **fields)` — il
n'en a aucun.

### 2. Appariement source ↔ base

- **Avec dossard** — clé `(course_id, bib_number)`, celle de la contrainte
  d'unicité `uq_participation_bib`. Sans ambiguïté.
- **Sans dossard** — par athlète, et **seulement si cet athlète n'a qu'une seule
  participation sur cette course**. Deux occurrences ou plus (la même personne
  peut légitimement figurer plusieurs fois dans les résultats source) : rien ne
  permet de savoir quelle ligne source correspond à quelle ligne en base, on ne
  devine pas et on conserve le comportement actuel (skip via le décompte
  multiset). Ce cas concerne les chronométreurs sans dossard (Sportinnovation).

### 3. Fusion prudente, champ par champ

Un champ n'est écrasé que si la source apporte une valeur **non vide**. Un
`total_time` de `01:23:45` survit donc à une page source temporairement amputée
(chronométreur en maintenance, recalcul en cours).

« Vide » se définit strictement : `None`, chaîne vide, dict vide. **`False` et `0`
n'en sont pas** — un `is_relay=False` est une affirmation du scraper, pas une
absence, et doit pouvoir corriger un `True` erroné. Un test de vérité pythonien
(`if valeur:`) confondrait les deux ; la comparaison se fait donc explicitement.

Contrepartie assumée : une suppression **volontaire** à la source (un classement
retiré après disqualification) ne se propage pas. C'est le prix de la protection
contre les régressions de source, jugé bon marché ici : une valeur erronée
conservée se corrige à la main, une valeur correcte détruite en masse ne se
récupère pas.

**`status` est traité à part**, car il n'est jamais vide (`mapping.derive_status`
renvoie toujours `finisher`, `DNF` ou `DNS`) : la règle « vide n'écrase pas » ne
le protégerait donc pas.

- Statut **explicite** du scraper (`scraped.status` renseigné) → il écrase. Le
  chronométreur affirme un DNF/DNS : c'est une information, pas une absence.
- Statut **absent** de la source → re-dérivé du `total_time` **fusionné**, jamais
  du scrapé seul.

Sans cette seconde règle, une source ayant temporairement perdu le temps total
produirait `derive_status → DNF` : le temps survivrait (vide n'écrase pas) mais
le statut basculerait, donnant un DNF avec un chrono. Incohérent.

### 4. Compteurs

Trois issues **exclusives** par ligne source :

| Compteur | Sens |
| --- | --- |
| `imported` | Participation créée. |
| `updated` | Participation existante dont **au moins un champ a changé**. |
| `skipped` | Participation existante déjà à jour (aucun champ à écrire), ou sans dossard et ambiguë. |

`skipped` garde donc son sens de « déjà en base », précisé en « déjà en base
**et à jour** ». La comparaison champ à champ, nécessaire pour distinguer
`updated` de `skipped`, évite au passage des `UPDATE` inutiles sur des milliers
de lignes inchangées.

Propagation de `updated`, de bout en bout :

- `import_service` — phases SSE `saving` et `done`, et le retour de
  `import_event` ; le retour « cached » de `_cached_result` porte `updated: 0`.
- `services/batch.BatchTotals` → `SheetOutcome` et `RescrapeOutcome` (charge
  utile `--json` : champ additif).
- `cli/reports` — nouvelle ligne « Participants mis à jour ».
- Front — `lib/types.ts` (`ImportProgressEvent`) et
  `components/scrape/ImportProgress.tsx`, qui affiche aujourd'hui
  « X importés · Y ignorés ».

`est_echec_total` n'est pas touché : il compare des **épreuves**, pas des
participants.

### 5. Effet réparé

La course en direct se met enfin à jour : le TTL de 10 minutes re-scrapait déjà,
c'est la persistance qui jetait le résultat. Aucun changement au cache lui-même.

## Tests

- **`_Persister`** — un temps corrigé à la source met à jour la participation ;
  un champ vide à la source n'écrase pas la base ; une ligne identique compte en
  `skipped` sans `UPDATE` ; un athlète sans dossard en un seul exemplaire est mis
  à jour ; le même en deux exemplaires ne l'est pas ; un statut explicite écrase ;
  un statut absent est re-dérivé du temps fusionné (le finisher amputé reste
  finisher) ; `is_relay=False` corrige bien un `True` en base (`False` n'est pas
  une valeur vide).
- **`import_service`** — les phases `saving`/`done` portent `updated`.
- **`batch` / services de batch** — `updated` remonte dans les totaux et les deux
  `Outcome`.
- **`cli/reports`** — la ligne « Participants mis à jour » est rendue.
- **Front** — `ImportProgress` affiche les trois compteurs.

## Hors périmètre

- **Suppression des participants disparus de la source.** Un participant retiré
  des résultats reste en base. Autre problème (détection de disparition vs page
  source partielle), autre spec.
- **Historisation des corrections.** On écrase, on ne conserve pas la valeur
  précédente.
- **Cache TTL.** Inchangé.
