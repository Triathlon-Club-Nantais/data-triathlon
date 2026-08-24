# Réconciliation de l'identité d'athlète au re-scrape — conception

**Issue** : #66 — `split_athlete_name` : changement de sémantique partagé.
**Date** : 2026-07-19.
**Branche** : `66-fix/split-athlete-name-donnees-existantes`.

Mesures faites sur `backend/triathlon.db` (30 536 athlètes, 91 épreuves), qui
est de la donnée réelle issue des liens scrapés — pas un jeu de dev synthétique.

---

## 1. Le problème, corrigé de ses deux erreurs d'énoncé

`split_athlete_name` (`scrapers/utils.py:96`) a gagné une branche sur la
branche 50 : quand `parts[0]` n'est pas en majuscules mais `parts[-1]` l'est
(forme « Prénom NOM »), le nom prend **tout** le bloc majuscule au lieu du seul
dernier token.

```
« Jean DE LA TOUR »   avant : ("TOUR", "Jean DE LA")   après : ("DE LA TOUR", "Jean")
```

La branche « NOM Prénom » (Wiclax, TimePulse) est **inchangée à l'octet près**.
Wiclax n'appelle d'ailleurs la fonction qu'en repli, quand `Name` et
`FirstName` sont tous deux absents (`wiclax.py:89-93`).

L'issue avance deux craintes. Les deux sont fausses, et il faut le dire pour
que la solution ne soit pas dimensionnée sur un risque imaginaire.

**« Un `rescrape-db` produirait des doublons sous `UNIQUE(nom, prenom,
birth_date)` ».** La contrainte ne mord jamais : `birth_date` est NULL sur
30 364 / 30 364 lignes, et en PostgreSQL deux NULL n'entrent pas en conflit
d'unicité. Le dédoublonnage réel est assuré par
`athlete_repository.get_by_identity`, pas par la contrainte. Aucune erreur
d'insertion n'est donc possible par ce chemin.

**« Un `rescrape-db` mettrait tout à jour ».** Il ne met rien à jour.
`import_service.py:87-99` : quand le dossard est déjà en base, la ligne fait
`return` **avant** `get_or_create_athlete` (ligne 102). L'athlète n'est même
jamais résolu, `split_athlete_name` jamais rappelé. `force=True` ne change rien
à ce chemin — il ne saute que le cache TTL (`import_event:156`).

**Le défaut réel** est donc l'inverse d'une explosion : c'est un **gel**. Les
graphies fautives sont figées à vie, et chaque nouvelle épreuve empile la
graphie corrigée à côté. Sans intervention explicite, la divergence ne s'éteint
pas — elle s'aggrave.

## 2. Volumétrie

| Mesure | Valeur |
| --- | --- |
| Athlètes (`nom` non vide) | 30 364 |
| Portant la signature de l'ancien découpage | 529 |
| — dont **ambigus**, à exclure | 26 |
| **Périmètre sûr** | **503** |
| — renommages simples | 414 |
| — fusions avec un athlète déjà correct | 89 |
| — conflits `(course, dossard)` | **0** |
| Participations concernées | 693 |
| Épreuves à re-scraper pour les couvrir | **14** (sur 91) |
| Athlètes orphelins aujourd'hui | **0** |
| Athlètes orphelins produits par la réconciliation | **503** |

Provenance des 503 : exclusivement Wiclax / ChronoSmetron
(`chronosmetron.wiclax-results.com`, `www.chronosmetron.com`,
`www.chronosmetron.wiclax-results.com`).

**Les 26 ambigus** sont des athlètes dont le prénom est déjà stocké en
majuscules par un fournisseur à champs séparés — `("BERGE", "LOLA")`. Leur
« correction » donnerait `("LOLA BERGE", "")`, c'est-à-dire la destruction du
prénom. C'est l'ambiguïté irréductible que documente la docstring de
`split_athlete_name` (« JP ROUX »), pas un bug à corriger. 3 d'entre eux
seulement sont portés par les 14 épreuves Wiclax ; les 23 autres sont hors
d'atteinte de tout re-scrape.

**Garde structurante** : ne jamais appliquer une correction qui vide le prénom.

## 3. Décision : réconcilier au re-scrape, pas réparer par script

Trois voies ont été pesées.

**Une commande CLI de réparation** (`fix-athlete-names --dry-run`) : opère hors
réseau, couverture 100 %, déterministe. Écartée — elle laisse intact le défaut
de fond (les données restent gelées), et c'est de la dette : un outil qui
n'existe que pour un incident unique.

**Une migration Alembic** : s'applique au déploiement, sans accès shell.
Écartée — 503 mutations validées à l'aveugle, dont 89 destructrices, avec un
`downgrade` impossible à écrire honnêtement.

**Faire réconcilier `rescrape-db`** — retenue. Le coût qu'on lui prêtait
n'existe pas (14 épreuves), les 89 fusions se résolvent d'elles-mêmes via
`get_or_create_athlete`, et surtout elle corrige la cause plutôt que le
symptôme : tout futur changement de sémantique d'un scraper sera absorbé par un
re-scrape au lieu de figer une strate de plus.

### La frontière : l'identité, rien d'autre

La réconciliation réécrit **`participation.athlete_id` et lui seul**. Temps,
rangs, statuts, splits d'une participation existante restent intouchés.

Cette frontière n'est pas arbitraire, et c'est le cœur de la décision : une
**identité** périmée fragmente une entité — Audrey LE BERRE figure deux fois
dans la liste du club, ses résultats éparpillés sur deux fiches. Un **temps**
périmé n'est qu'une valeur fausse à un endroit. Seule la première nature de
défaut justifie qu'on touche maintenant à des lignes déjà persistées.

**Hors périmètre, explicitement** : « la source doit-elle pouvoir réécrire les
temps, les rangs, les corrections manuelles ? » est une question de fond
(idempotence contre additivité) qui mérite son issue. Elle n'est pas tranchée
ici, et ce silence est délibéré.

## 4. Conception

### 4.1 Le repli de `_Persister.add`

`import_service.py:87-99` cesse de sortir sèchement sur dossard connu :

```
dossard déjà en base
  → résoudre l'athlète (get_or_create_athlete)
  → si participation.athlete_id ≠ athlete.id : réassigner, compter « réconciliée »
  → sinon : skipped, comme aujourd'hui
```

Le compteur `skipped` garde son sens (participant déjà en base, rien à faire) ;
les réassignations sont comptées à part.

**Conséquence sur les données chargées.** Le repli a besoin des
**participations**, pas seulement de leurs dossards.
`participation_repository.existing_bibs_for_course` devient
`existing_participations_for_course` → `dict[bib, Participation]`. L'ensemble
des dossards s'en déduit ; les autres appelants (`_cached_result:143`,
`finalize`) conservent leur sémantique.

**Conséquence sur le coût.** Le chemin de repli devient coûteux là où il ne
faisait rien : une résolution d'athlète par ligne déjà en base, soit de l'ordre
de 30 000 `get_by_identity` sur un `rescrape-db` complet. C'est tolérable pour
une commande de batch, mais c'est un changement de profil réel — il est
documenté ici pour ne pas être découvert au chronomètre.

### 4.2 Les orphelins

**503** anciennes graphies se retrouveront sans participation — les 414
renommages *et* les 89 fusions, puisque dans les deux cas la participation
quitte l'ancienne fiche. Aucune des 503 cibles ne porte de participation en
dehors des 14 épreuves re-scrapées : elles sont donc toutes intégralement
vidées, sans reliquat.

Nettoyage **une fois en fin de batch**, dans `rescrape_service` après
`run_batch` — jamais par épreuve : un athlète orphelin après l'épreuve A peut
être ré-attaché par l'épreuve B plus loin dans la même passe.

Deux faits rendent la règle « supprimer les athlètes sans participation »
défendable :

- `Participation.athlete_id` est la **seule** FK vers `Athlete` (vérifié sur
  `app/models/`) ; aucune autre table ne dépend de la ligne supprimée ;
- il y a **exactement 0 orphelin en base aujourd'hui**, donc la règle est un
  no-op sur l'existant : elle ne peut emporter que ce que la réconciliation
  vient de libérer.

Le nombre d'orphelins supprimés figure au bilan.

### 4.3 Le `--dry-run` (option D1)

`rescrape-db --dry-run` existe déjà, avec une **autre** promesse : il liste les
URLs ciblées et sort avant tout scraping (`rescrape_service.py:137-141`).

| | Avant | Après (D1) |
| --- | --- | --- |
| Nature | aperçu de **sélection** | aperçu de **réécriture** |
| Réseau | non | oui |
| Sortie | liste d'URLs | liste d'URLs + `avant → après` |

`--dry-run` devient « **ne persiste rien** » : il scrape, calcule les
réassignations, les rend au bilan, puis annule la transaction sans commit.

Le flag promet « ce qui se passerait » ; aujourd'hui il sous-livre. Le coût
réseau est le prix d'un aperçu véritable, et `--limit` / `--url` le bornent —
pour les 14 épreuves qui nous occupent, il est trivial.

**Régression assumée** : un `--dry-run` global devient aussi long qu'un vrai
passage, et l'usage « qu'est-ce que je ciblerais ? » perd sa gratuité. La liste
d'URLs restant affichée, cet usage n'est pas perdu, seulement ralenti.

**Mécanique du non-commit** : le dry-run doit traverser tout le chemin de
persistance pour calculer les réassignations, puis `db.rollback()` au lieu de
`db.commit()`. Le batch commitant chaque épreuve séparément
(`batch._import_one`), le drapeau doit descendre jusque-là — ce n'est pas un
court-circuit en amont comme aujourd'hui.

### 4.4 Le bilan

Un bloc détaillé sur le modèle de `failures` (`cli/reports._lignes_echecs`),
borné aux seules réassignations, donc léger :

```
Participations réconciliées : 693
Athlètes fusionnés          : 89
Athlètes orphelins supprimés: 503
Identités réconciliées (détail) :
  - BERRE | Audrey LE  ->  LE BERRE | Audrey   (12 participations)
```

Champs ajoutés à `RescrapeOutcome`, donc repris tels quels dans `--json` via
`asdict()`. Unités nommées, conformément à la règle d'`AGENTS.md` : on compte
des **participations** et des **athlètes**, jamais des « lignes ».

## 5. Tests

Sans réseau, conformément à la convention du dépôt.

| Cible | Garde |
| --- | --- |
| `_Persister.add` | dossard connu + athlète divergent → `athlete_id` réassigné, compteur incrémenté |
| `_Persister.add` | dossard connu + athlète identique → aucune écriture, `skipped` inchangé |
| `_Persister.add` | fusion : la cible existe déjà → réassignation vers l'existant, pas de création |
| Orphelins | athlète vidé de ses participations → supprimé ; athlète encore rattaché → conservé |
| Orphelins | exécution sur une base sans orphelin → no-op (garde de non-régression) |
| `--dry-run` | aucune écriture persistée, mais détail des réassignations non vide |
| Garde des ambigus | une correction qui viderait le prénom n'est jamais appliquée |
| Non-régression | `split_athlete_name("Jean DE LA TOUR") == ("DE LA TOUR", "Jean")` |

Le dernier point est une garde vivante : il fige la sémantique qui a motivé
toute cette conception.

## 6. Documentation

`AGENTS.md`, section CLI, doit acter trois choses que le code ne dit pas :

1. `rescrape-db` **réconcilie l'identité d'athlète** sur les participations
   existantes — il n'est plus purement additif ;
2. il ne réconcilie **que** l'identité, et ce silence sur les temps et les
   rangs est délibéré (§3) ;
3. `--dry-run` a changé de nature : il scrape désormais, et ne persiste rien.

## 7. Ce que cette conception ne fait pas

- Elle ne répare pas les **23 ambigus hors des 14 épreuves Wiclax**. Ils
  resteront tels quels, et c'est le comportement voulu : les corriger
  détruirait leur prénom.
- Elle ne garantit pas la réparation des 503 : elle dépend des 14 épreuves
  encore scrapables au moment du passage. Une épreuve devenue inaccessible
  laissera ses lignes gelées. Le bilan le dira (`failures`), mais la couverture
  n'est pas de 100 % — c'est le prix payé pour corriger la cause plutôt que le
  symptôme, et c'est un arbitrage assumé, pas un angle mort.
- Elle ne rend pas `rescrape-db` idempotent sur les **valeurs** (temps, rangs,
  statuts). Voir §3, « hors périmètre ».
