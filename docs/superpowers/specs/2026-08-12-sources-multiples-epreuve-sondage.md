# Sondage — règle de rapprochement des épreuves publiées par deux chronométreurs

**Date** : 2026-08-12 — **Issue** : #277 (lot 0 de l'epic #275, bloque #289) — **Origine** : discussion #210, issue #268, #261

Ce fichier est un **sondage** au sens d'`AGENTS.md` : il consigne ce qui a été
mesuré sur le terrain à la date ci-dessus et **prime** sur la spec, le plan et le
design. Toute divergence se tranche en re-sondant, pas en argumentant.

## En premier : deux hypothèses de l'epic #275 sont démenties par la mesure

1. **« La clé actuelle `UNIQUE(name, event_date, event_type, is_relay)` ne collide
   jamais entre Klikego et Breizh Chrono »** — **faux aujourd'hui**. Sur les deux
   URLs de Mesquer 2026 citées par #210, les deux fournisseurs produisent
   **exactement la même identité**, champ par champ, y compris les accents du
   nom. Idem pour le Duathlon Nozéen 2026. Ces deux cas ne demandent **aucun**
   rapprochement : `get_or_create` les fusionne déjà. Il ne leur manque que
   l'enregistrement de la seconde URL — c'est #283, pas #289.

2. **« #296 — `_fetch_all_heats` suit un 302, le fan-out des heats ne se fait pas,
   et les parcours SwimRun de Mesquer n'ont jamais été scrapés »** — la racine
   Breizh Chrono **redirige bien** (mesuré : elle atterrit sur `swim-run-m-duo`
   pour Mesquer, sur `swimrun-court-duo` pour Dinard), mais la page de heat
   atterrie **porte la liste complète des heats** : `_fetch_all_heats` en découvre
   **8 sur Mesquer** (dont `swim-run-s-indiv` et `swim-run-s-duo`) et **13 sur
   Dinard**. Le fan-out se fait. L'effet de bord réel du 302 est ailleurs, et il
   est plus grave : c'est la **date** (voir Q3).

Le cas qui a réellement besoin d'un rapprochement automatique n'est donc pas le
couple Klikego / Breizh Chrono, mais **les deux façades du même Breizh Chrono** —
`resultats.` et `live.` — qui divergent sur `name` **et** `event_date`.

## Méthode et panel

Deux sources, aucune écriture.

**1. La base de dev du worktree** (`backend/triathlon.db`, copiée en `/tmp` avant
lecture) : **95 `Course`**, **20 125 `Participation`**, 10 fournisseurs,
`event_date` du 2024-09-22 au 2026-07-25, **0 `event_date IS NULL`**. Soit
**4 465 paires** de courses à examiner.

*Vérité terrain établie empiriquement, pas à l'œil* : aucune paire de courses de
cette base ne partage **≥ 50 %** de ses athlètes ; le recouvrement maximal observé
est de **34 %**, entre « Triathlon Sud Vendée — 6-9 Ans » et « Triathlon de
Vertou — Triathlon Jeunes », deux épreuves réellement distinctes. La base **ne
contient aucun doublon** : **toute** paire qu'une règle rapproche y est donc un
**faux positif**, sans ambiguïté d'interprétation.

**2. Le réseau**, via `app/core/http.client()` (garde SSRF) et les scrapers réels
du dépôt, en appelant `get_provider(url).scrape_event_all(url)` puis en groupant
les `ScrapedResult` par le quadruplet d'identité que `mapping.get_or_create_course`
transmet à `course_repository.get_or_create`. Le Sheet du club
(`sheet_source.DEFAULT_SHEET_URL`, 785 liens) a servi à retrouver les couples
d'URLs réels des trois cas.

## Q1 — les lignes `Course` des cas connus, et le champ qui diverge

### Mesquer 2026 — **aucune divergence** (identités identiques)

Identités produites *aujourd'hui* par un scrape réel de chaque URL de #210 :

| `name` | `event_date` | `event_type` | `is_relay` | Klikego | BC `resultats.` |
|---|---|---|---|---|---|
| Triathlon et SwimRun Mesquer-Quimiac 2026 | 2026-06-13 | `triathlon-s` | false | 498 part. | **498 part.** |
| Triathlon et SwimRun Mesquer-Quimiac 2026 | 2026-06-13 | `triathlon-xs` | false | 459 | — (heat non ciblé) |
| Triathlon et SwimRun Mesquer-Quimiac 2026 | 2026-06-13 | `triathlon-xs` | true | 40 | — |
| Triathlon et SwimRun Mesquer-Quimiac 2026 | 2026-06-13 | `swimrun-s` | false | 185 | — |
| Triathlon et SwimRun Mesquer-Quimiac 2026 | 2026-06-13 | `swimrun-m` | false | 58 | — |
| Triathlon et SwimRun Mesquer-Quimiac 2026 | 2026-06-13 | `triathlon` | false | 69 | — |

- URL Klikego : `www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/1677015306084-12?heat=triathlon-s-indiv` → fan-out sur 8 heats, **6 identités**.
- URL BC : `resultats.breizhchrono.com/resultats-courses/triathlon-et-swimrun-mesquer-quimiac-2026-1677015306084-12/triathlon-s-indiv` → **1 identité**, `('Triathlon et SwimRun Mesquer-Quimiac 2026', 2026-06-13, 'triathlon-s', False)`, **strictement égale** à celle de Klikego.
- Un fan-out BC complet (sans heat) produirait **les 6 mêmes identités** que Klikego. Divergence mesurée : **aucune**.
- La base de dev porte 5 lignes Mesquer, **toutes Klikego**, chacune un heat distinct — pas un doublon. Les 5 lignes de la preview décrites dans #210 (dont `id=38` en `swimrun-s` et `id=50` en `triathlon-s` avec la **même** `source_url`) ne se reproduisent plus : `classify_event_type('triathlon-s-indiv')` rend `triathlon-s` de façon stable sur les deux fronts.

**Pourquoi les noms coïncident au caractère près** : les deux fronts partagent le
back-office décrit dans `backend/app/scrapers/klikego_platform.py`, et
`parse_event_name` (`:66`) lit le nom dans le **même `<title>`**, en retirant le
préfixe de heat que BC y ajoute. Ce n'est pas une coïncidence de libellé, c'est la
même chaîne, lue au même endroit.

### Duathlon Nozéen — **aucune divergence** sur 2026, source BC **morte** sur 2025

| Édition | `name` | `event_date` | `event_type` | `is_relay` | part. | fournisseurs |
|---|---|---|---|---|---|---|
| 2026 | 6e Duathlon Nozéen 2026 | 2026-04-12 | `duathlon-s` | false | 166 | **Klikego ET BC : identité identique** |
| 2026 | 6e Duathlon Nozéen 2026 | 2026-04-12 | `duathlon-s` | true | 15 | Klikego |
| 2026 | 6e Duathlon Nozéen 2026 | 2026-04-12 | `duathlon-xs` | false | 14 | Klikego |
| 2025 | 5e Duathlon Nozéen 2025 | 2025-04-13 | `duathlon-s` | false | 355 | Klikego |
| 2025 | 5e Duathlon Nozéen 2025 | 2025-04-13 | `duathlon-s` | true | 12 | Klikego |

- URLs : `www.klikego.com/resultats/6e-duathlon-nozeen-2026/1517534975128-8?heat=duathlon-s---open` et `resultats.breizhchrono.com/resultats-courses/6e-duathlon-nozeen-2026-1517534975128-8/duathlon-s---open` → identités **strictement égales**, 166 participations de part et d'autre.
- L'URL BC de l'édition 2025 présente dans le Sheet
  (`www.breizhchrono.com/detail-de-la-course/5eduathlonnozeen-…-2025-18389`) rend
  aujourd'hui un **404 Wix**. La façade `www.breizhchrono.com` est morte : elle
  porte **93 des 785 liens** du Sheet, et n'a d'ailleurs aucune branche de
  parsing dédiée dans le scraper.
- Le doublon de #261 était donc **historique** ; il ne se reproduit pas par re-scrape.

### Vertou 2026 — **4 URLs, une seule identité par parcours**

Les 4 formes d'URL du Sheet ont été scrapées : elles rendent **les 9 mêmes
identités**, au caractère et au jour près.

| `name` | `event_date` | `event_type` | `is_relay` | part. |
|---|---|---|---|---|
| Triathlon de Vertou - S-Open | 2026-05-03 | `triathlon-s` | false | 351 |
| Triathlon de Vertou - S-Cad-Jun PDL | 2026-05-03 | `triathlon-s` | false | 120 |
| Triathlon de Vertou - S-Open Femmes | 2026-05-03 | `triathlon-s` | false | 77 |
| Triathlon de Vertou - Relais S | 2026-05-03 | `triathlon-s` | true | 28 |
| Triathlon de Vertou - XS-Open | 2026-05-03 | `triathlon-xs` | false | 108 |
| Triathlon de Vertou - XS-Benj-Mini PDL | 2026-05-03 | `triathlon-xs` | false | 106 |
| Triathlon de Vertou - Relais XS | 2026-05-03 | `triathlon-xs` | true | 5 |
| Triathlon de Vertou - Duathlon Jeunes | 2026-05-03 | `duathlon` | false | 39 |
| Triathlon de Vertou - Triathlon Jeunes | 2026-05-03 | `triathlon` | false | 32 |

Les 4 URLs : `chronosmetron.wiclax-results.com/Triathlon%20de%20Vertou%202026/`,
la même avec `www.`, `www.chronosmetron.com/754-triathlon-de-vertou-2026`, et
`…/G-Live/g-live.html?f=../Triathlon%20de%20Vertou%202026/Triathlon%20de%20Vertou.clax`.
Seule la `source_url` diffère. **Vertou n'est pas un cas de rapprochement** : c'est
le cas d'école de « N sources, une active » (#278, #283, #284) — le rapprochement
n'a rien à faire, la clé d'identité fait déjà le travail.

### Le cas qui diverge vraiment : **Dinard 2025, deux façades du même fournisseur**

C'est le seul couple mesuré où l'identité **ne** collide pas. `live.` est en base
(13 lignes), `resultats.` a été scrapé pour comparaison.

| Champ | via `live.breizhchrono.com` (en base) | via `resultats.breizhchrono.com` (mesuré) |
|---|---|---|
| `name` | `Triathlon SwimRun Dinard Côte d'Emeraude - Swimrun Court Duo` (**événement + heat, sans millésime**) | `Triathlon SwimRun Dinard Côte d'Emeraude 2025` (**événement + millésime, sans heat**) |
| `event_date` | **par heat** : 09-12 (trail), 09-13 (Découverte, Longue Distance), 09-14 (Olympique, swimruns) | **09-12 pour les 13 heats** |
| `event_type` | identique | identique |
| `is_relay` | identique | identique |
| lignes `Course` | **13** (une par heat) | **8** (les 6 swimruns s'effondrent en une) |

**Trois champs divergent d'un coup** — `name`, `event_date`, et le *nombre* de
lignes. Un ré-import de Dinard via `resultats.` après `live.` ajouterait **8
lignes `Course` neuves**, sans en rapprocher aucune.

Pire, la façade `resultats.` produit **trois formes de nom différentes** dans le
même événement : `parse_event_name` ne retire le préfixe de heat que si
`_slugify(libellé) == heat`, et « Triathlon Longue Distance Overstim.s » se
slugifie en `…overstim-s` là où le heat vaut `…overstims` — d'où deux lignes
nommées `Triathlon Longue Distance Overstim.s - Triathlon SwimRun Dinard Côte
d'Emeraude 2025`, préfixe de heat compris.

## Q2 — l'identifiant d'événement partagé : **un seul couple sur les 14**

Inventaire fait en lisant les 14 modules de `backend/app/scrapers/` et
`registry.py`, pas au ressenti.

| Fournisseur | id d'événement dans l'URL | Forme | Namespace |
|---|---|---|---|
| **klikego** | oui | dernier segment de path (`registry.py:224`, positionnel) | **partagé avec breizhchrono** |
| **breizhchrono** | oui, sur les 3 façades | suffixe `(\d{10,}-\d+)$` du path (`breizhchrono.py:96`) ; `?ref=` (`:87`) ; `?reference=` (`:309`) | **partagé avec klikego** |
| chronoweb | oui | `?event=` (`chronoweb.py:171`) | privé (entier) |
| runnerbreizh | oui | `?CourseFichierGpsNom=` (`runnerbreizh.py:109`) | privé (nom de fichier GPS) |
| timepulse | oui | `?id_event=` ou dernier segment numérique (`timepulse.py:316`) | privé (entier) |
| prolivesport | oui | `?eventId=` ou `/result/{id}` (`prolivesport.py:176`) | privé (entier) |
| sportinnovation | oui | `/Resultats/(\d+)` ou slug du front 2026 (`sportinnovation.py:644`) | privé |
| sporthive | oui | snowflake ou GUID (`sporthive.py:95`) | privé (MyLaps) |
| chronoplace | partiel | slug + `/epreuve/{id}` optionnel (`chronoplace.py:91`) | privé |
| oktime | selon la forme | `/{id}/` sinon résolu (`oktime.py:70`, `:100`) | privé (post-id WordPress) |
| raceresult | selon la façade | 1er segment numérique (`raceresult.py:92`) ; `comp_uid` **délibérément ignoré** | privé (3 hosts, 1 provider) |
| competitor | selon le host | UUID sur `competitor.com`, résolu depuis `ironman.com` (`competitor.py:126`, `:132`) | privé (GUID) |
| t2area | oui, en slugs | triplet du calendrier FFTRI (`t2area.py:61`) | privé |
| **wiclax** | **non** | seulement un chemin de fichier `.clax` dans `?f=`, souvent absent (`wiclax.py:250`) | privé, **par déploiement** |

**Réponse** : un id d'événement est extractible syntaxiquement chez **13 des 14**
fournisseurs (wiclax excepté), mais il est **privé** partout sauf **un seul
couple** : Klikego ↔ Breizh Chrono, de forme `{epoch_ms}-{n}`. La preuve est dans
le code, pas dans l'URL : `klikego_platform._course_result_url` (`:147-151`)
envoie ce même id en paramètre `ref` de `/bc/resultats/course-result.jsp` **pour
les deux fronts**, et `breizhchrono._parse_live_slug` (`:332`) reconstruit un lien
`resultats-courses/{slug}-{id}/` depuis une page `live.`. Les **trois** façades
Breizh Chrono le portent, sous trois graphies.

**Piège dimensionnant, mesuré sur le Sheet** : le préfixe `{epoch_ms}` **n'est pas**
une clé d'événement, c'est une clé de **compte** chez la plateforme. Sur 785 liens
et 59 identifiants distincts, **40 préfixes** apparaissent, dont **12 portent
plusieurs éditions** — et `1488071608761` en porte **8, sur des événements sans
aucun rapport** (Dinard, Royan, Châteauroux…). Le suffixe `-{n}`, lui, distingue
l'édition : Mesquer `-6`/`-9`/`-12` pour 2024/2025/2026, Nozéen `-7`/`-8` pour
2025/2026. **Ne jamais tronquer l'id à son préfixe.**

**Portée réelle du critère** : sur les 59 identifiants du Sheet, **9 (15 %) sont
portés par les deux fournisseurs**, et **2** apparaissent sur deux façades Breizh
Chrono distinctes. En base de dev, **30 des 95 courses** portent un id de
plateforme dans leur `source_url` (15 Klikego, 15 Breizh Chrono) ; les 65 autres
n'en portent aucun.

## Q3 — `event_date` n'est **pas** exploitable comme critère

Trois mesures, toutes négatives :

1. **La façade `resultats.` n'a qu'une date pour tout l'événement.**
   `scrape_event_all` (`breizhchrono.py:228-235`) lit la date **une fois**, sur la
   page pointée — et sans heat, c'est la **racine**, qui **redirige** vers un heat
   arbitraire. Mesuré sur Dinard : la racine atterrit sur `swimrun-court-duo` et
   rend `2025-09-12`, alors que ce heat court le **14**. Les 13 heats reçoivent
   `2025-09-12`. Vérifié heat par heat : les 13 pages rendent toutes `2025-09-12`.
2. **La façade `live.` a une date par heat.** `_parse_live_index` (`:352`) lit une
   date par carte de heat depuis `index.jsp` — la seule page live qui en porte —
   avec le repli `default_date = min(dates_by_heat.values())` (`:414`). Sur Dinard
   elle rend correctement 09-12 / 09-13 / 09-14.
   → **Pour un événement pluri-journalier, les deux façades du même fournisseur
   divergent par construction, jusqu'à 2 jours.**
3. **`_parse_bc_date` (`:51-70`) prend la *première* date trouvée dans tout le
   HTML** (`re.search(r'(\d{4}-\d{2}-\d{2})', html)`), sans ancrage sur le
   moindre élément. Sur la racine Dinard, le HTML contient `2025-09-12` **et**
   `2025-09-14` : la valeur retenue dépend de l'ordre du balisage.

Contrepoint honnête : `event_date IS NULL` est à **0 sur 95** en base de dev. Le
problème n'est donc pas l'absence de date, c'est qu'une date **présente et
plausible** peut être fausse de un à deux jours. Une tolérance ±3 j ne coûte
**aucun faux positif** sur cette base (mesuré, voir plus bas) mais ne rapproche
**rien** non plus, parce que le nom, lui, diverge. La date ne peut donc être
qu'un **garde-fou**, jamais un critère porteur.

## Q4 — une normalisation de `name` ne suffit pas : la divergence est de **granularité**

Ce n'est pas une affaire de casse, d'accents ou de millésime — c'est que les
fournisseurs ne nomment pas la **même chose**.

| Convention de nommage | Fournisseurs mesurés |
|---|---|
| `name` = **événement** (le heat n'est porté que par `event_type` / `is_relay`) | klikego, **breizhchrono via `resultats.`**, timepulse |
| `name` = **événement + heat** | **breizhchrono via `live.`**, wiclax, raceresult, sporthive, sportinnovation, chronoplace, chronoweb, oktime |

Aucune normalisation de chaîne ne franchit cette frontière. Pour faire coïncider
`Triathlon SwimRun Dinard Côte d'Emeraude 2025` avec `… - Swimrun Court Duo`, il
faut **retirer le suffixe de heat** — et cette opération est **destructrice** :
elle rapproche alors aussi `Swimrun Court Solo`, `Swimrun Medium ZOGGS Duo`,
`Swimrun Long Super U Pleurtuit Solo`… Mesuré : **53 faux positifs** (voir R6).

Là où les deux fournisseurs nomment au même niveau (Klikego ↔ `resultats.`), les
noms sont **déjà identiques au caractère près** : aucune normalisation n'est
nécessaire. Là où ils nomment à des niveaux différents, aucune normalisation ne
suffit. Dans les deux cas, `name` est inutile comme critère.

## La règle de rapprochement

Écrite pour être implémentée sans reposer de question. Elle ne compare **ni**
`name`, **ni** `event_date`, **ni** `event_type`, **ni** `is_relay` — les quatre
sont mesurés inaptes.

> **Règle R.** Deux `Course` désignent la même épreuve si et seulement si les
> **quatre** conditions suivantes sont vraies :
>
> 1. `provider` de chacune ∈ `{"klikego", "breizhchrono"}` ;
> 2. `platform_event_id(source_url)` est **non vide** et **égal** de part et d'autre ;
> 3. `heat_slug(source_url)` est **non vide** et **égal** de part et d'autre ;
> 4. les deux `Course` sont distinctes (`id` différents).
>
> Sinon : **pas de rapprochement automatique**. Aucune tolérance, aucun repli,
> aucun score.

**`platform_event_id(url)`** — l'identifiant de plateforme **entier**, suffixe
d'édition compris. Ne pas écrire une nouvelle regex : réutiliser les parseurs
existants, qui couvrent les quatre formes.

| Forme d'URL | Extraction | Référence |
|---|---|---|
| `klikego.com/resultats/{slug}/{id}` | dernier segment de path | `registry.py:224` |
| `resultats.breizhchrono.com/resultats-courses/{slug}-{id}/{heat}` | `re.search(r"(\d{10,}-\d+)$", path_parts[1])` | `breizhchrono.py:96` |
| `…/bc/resultats/coureur.jsp?ref={id}` | query `ref` | `breizhchrono.py:87` |
| `live.breizhchrono.com/external/live5/*.jsp?reference={id}` | query `reference` | `breizhchrono.py:309` |

Chaîne vide si aucune forme ne matche. **Interdit** : tronquer au préfixe
`{epoch_ms}` (mesuré : 12 préfixes sur 40 portent plusieurs éditions, un en porte
8 événements sans rapport).

**`heat_slug(url)`** — le slug du heat, en minuscules :
1. paramètre de query `heat` s'il est présent (Klikego et `live.`) ;
2. sinon, 3<sup>e</sup> segment de path de `/resultats-courses/{slug}-{id}/{heat}` ;
3. sinon chaîne vide.

**Comparaison** : égalité **octet par octet après `lower()`** — rien d'autre. Ni
accents retirés (les slugs sont déjà ASCII), ni ponctuation normalisée : le triple
tiret est **porteur de sens** (`_detect_relay` teste `heat_slug.endswith("---")`,
`breizhchrono.py:170`), et `duathlon-s---open` ≠ `duathlon-s---en-relais`.

**Sur quelle `source_url` la règle s'applique** : celle que le **scraper** pose sur
chaque `ScrapedResult` après fan-out, jamais l'URL soumise par l'utilisateur. Les
deux scrapers la construisent par heat — `breizhchrono.py:188` pour `resultats.`,
`:426-429` pour `live.`, et le fan-out Klikego pour `?heat=`. Une URL soumise au
niveau événement n'a pas de heat, et la règle ne s'y applique donc pas.

**Rien à stocker** : la règle se calcule depuis `source_url`. Une colonne
`external_event_id` n'apporterait rien de plus et ajouterait une migration.

### Vérification de la règle sur les couples mesurés

| Couple | Attendu | Règle R |
|---|---|---|
| Mesquer 2026 `triathlon-s-indiv` — Klikego / BC `resultats.` | rapprocher | **oui** (`1677015306084-12` + `triathlon-s-indiv`) |
| Nozéen 2026 `duathlon-s---open` — Klikego / BC `resultats.` | rapprocher | **oui** (`1517534975128-8` + `duathlon-s---open`) |
| Dinard 2025 `swimrun-court-duo` — BC `live.` / BC `resultats.` | rapprocher | **oui** (`1488071608761-688` + `swimrun-court-duo`) |
| Mesquer `triathlon-s-indiv` vs `triathlon-xs-indiv` (**heats distincts**) | ne pas rapprocher | **non** (heats différents) |
| Nozéen 2025 vs 2026 (**éditions successives**) | ne pas rapprocher | **non** (`-7` ≠ `-8`) |
| Vertou, 4 formes wiclax | ne pas rapprocher | **non** (aucun id de plateforme) |

Les deux pièges nommés par #277 sont écartés **par construction**, pas par
réglage : le heat est dans la clé, et l'édition est dans l'id.

## Taux de faux positifs, mesuré sur la base de dev entière

95 courses, **4 465 paires**, aucun doublon réel (cf. « Méthode »). Toute paire
rapprochée est donc un faux positif. Normalisation de `name` employée pour les
règles candidates : NFKD sans diacritiques, minuscules, ordinal d'édition de tête
(`^\d+\s*(er|ere|eme|e)\b`) retiré, ponctuation → espaces, espaces compactés ;
`drop_year` retire tout `\b(19|20)\d{2}\b`, `drop_heat_suffix` ne garde que ce qui
précède le premier ` - `.

| Règle candidate | Faux positifs / 4 465 | Dont éditions ≠ | Dont heats ≠ du même événement |
|---|---|---|---|
| R1 — `name` normalisé seul (**l'énoncé littéral de l'epic**) | **37** | 1 | 20 |
| R2 — R1 + millésime retiré | **37** | 1 | 20 |
| R3 — `name` normalisé + `event_type` + `is_relay` + date exacte | **0** | 0 | 0 |
| R4 — R3 + tolérance ±1 j | **0** | 0 | 0 |
| R5 — R3 + tolérance ±3 j | **0** | 0 | 0 |
| R6 — R5 + suffixe de heat retiré | **53** | 0 | 0 |
| R6b — R6 + millésime retiré | **53** | 0 | 0 |
| **R (retenue)** — id de plateforme + slug de heat | **0** | 0 | 0 |

Ventilation des faux positifs, pour montrer **quoi** casse :

- **R1 / R2 — 37 paires.** `LE NORTH MAY` 15 paires (6 heats timepulse), `Mesquer
  2026` 10, `Vierzon 2026` 10, `Spay'cific Races 2025 - SwimRun` 1 (solo vs relais),
  et **`Triathlon de Nantes` 1** — la seule paire **inter-fournisseurs**, et c'est
  précisément le pire cas : `2025-10-19` timepulse contre `2026-05-16` klikego,
  deux éditions **et** deux épreuves différentes, rapprochées par le nom seul.
  Retirer le millésime ne change rien (37 → 37) : les noms concernés n'en portent
  pas de discriminant.
- **R6 / R6b — 53 paires.** `Genève Triathlon` 22 (13 contests RaceResult),
  `Dinard` 15 (les 6 swimruns), `Carnac 2025` 6 (4 aquathlons de catégories
  d'âge), `Vertou` 4, `Lacanau 2026` 3, `La Roche` 2, `Sud Vendée` 1. Retirer le
  suffixe de heat **multiplie les faux positifs par 1,4 par rapport au nom nu**,
  tout en n'étant la seule voie possible pour rapprocher Dinard : le compromis
  n'existe pas.
- **R (retenue) — 0.** Et 0 également en n'appliquant pas le garde-fou sur
  `provider` : le motif `(\d{10,}-\d+)` n'a matché **aucune** des 65 courses
  non-Klikego de la base (ni sporthive, ni wiclax, ni raceresult, ni oktime…). Le
  garde-fou reste néanmoins recommandé — il rend l'intention explicite plutôt
  qu'accidentelle.

**Précaution de lecture** : ces taux valent sur **95** courses. Pour une règle
fondée sur le nom, le nombre de paires croît en O(n²) : sur une base 10 fois plus
grande, les 37 faux positifs de R1 ne deviennent pas 370, ils deviennent
davantage. Le taux de R, lui, ne dépend pas de la taille : il ne rapproche que
des couples `(id, heat)` strictement égaux.

## Ce que la règle ne couvre pas — et qui reste au geste manuel

Assumé, mesuré, et à traiter par #287 (fusion manuelle) / #288 (doublons suspects) :

1. **Les 12 autres fournisseurs.** Aucun ne partage d'identifiant avec un autre.
   Un même événement publié par, disons, wiclax **et** timepulse ne sera jamais
   rapproché automatiquement. Aucun cas de ce type n'existe dans la base de dev ;
   le seul indice est une paire de noms homonymes (`Triathlon de Nantes`) qui
   n'est **pas** un doublon.
2. **Wiclax, sans identifiant d'événement du tout.** Les 4 formes d'URL de Vertou
   ne sont réconciliables que par le fichier `.clax` visé, souvent absent de
   l'URL et résolu par jusqu'à 3 sauts réseau (`wiclax.py:203`). Sans objet ici :
   les 4 formes produisent déjà **la même** identité.
3. **La façade `www.breizhchrono.com`, morte (404 Wix).** 93 liens du Sheet, aucun
   heat ni id exploitable dans ses URLs `detail-de-la-course/…`.
4. **Un heat effondré sur un autre.** Quand deux heats partagent
   `(name, event_type, is_relay)` — Mesquer `swim-run-s-duo` + `swim-run-s-indiv`,
   les 6 swimruns de Dinard via `resultats.` — la `Course` survivante ne porte que
   la `source_url` du **premier** heat traité. La règle **sous-**rapproche alors
   (elle n'invente pas de faux positif, mais elle rate le vrai). Cause racine :
   `_detect_relay` ignore « duo » (#295). À corriger **avant** #289, sinon le
   rapprochement automatique héritera d'un heat_slug arbitraire.
5. **La reclassification d'`event_type`** (#294) : hors de portée de la règle, qui
   ne regarde pas `event_type`. Sans #294, le nettoyage de #293 se défera.
6. **La divergence de `name` et d'`event_date` entre les deux façades Breizh
   Chrono** subsiste **après** rapprochement : la règle dit « c'est la même
   épreuve », elle ne dit pas quel nom ni quelle date garder. C'est la décision D2
   (« la source active fait foi, remplacement total ») qui tranche, pas ce sondage.

## Ce qui n'a pas pu être mesuré

**L'accès à la base preview (et à la production) n'était pas disponible pour ce
sondage.** Tout ce qui précède est mesuré sur la base de **dev** du worktree
(95 courses) et sur le **réseau réel**. Ce n'est pas une mesure preview, et il ne
faut pas la lire comme telle. Restent à re-vérifier sur preview, avant #289 :

1. **Le taux de faux positifs de la règle R sur la preview entière.** La règle
   étant fondée sur une égalité exacte de `(id, heat)`, on attend 0, mais le
   nombre de paires y est plus grand et l'historique y contient des `source_url`
   plus anciennes. **C'est la seule mesure qui doit être refaite à l'identique.**
2. **Le rappel — impossible à mesurer sur dev.** La base de dev **ne contient
   aucun doublon** (0 paire au-delà de 34 % d'athlètes communs). Le rappel de R
   n'a donc pu être vérifié que sur 3 couples reconstitués depuis le réseau, où il
   vaut 3/3. Sur preview, il faut lister les vrais doublons (par recouvrement
   d'athlètes ≥ 50 %, la méthode de ce sondage) et compter combien R en attrape.
3. **Les 5 lignes Mesquer de #210** (`id` 38, 50, 52, 53, 54), et en particulier le
   couple `id=38` (`swimrun-s`) / `id=50` (`triathlon-s`) qui partage la **même**
   `source_url`. Un re-scrape ne les reproduit plus : il faut vérifier si elles
   sont **encore** là (auquel cas c'est de la dette de données à nettoyer par
   #293) ou déjà résorbées.
4. **Combien de `Course` de la preview portent un id de plateforme extractible**
   dans leur `source_url`. En dev : 30 sur 95 (32 %). Ce ratio borne
   mécaniquement la portée de #289.
5. **La proportion de `Course` en `event_date IS NULL`** sur preview. En dev :
   **0 sur 95**. Si preview en porte, le repli
   `default_date = min(dates_by_heat.values())` a laissé des traces qu'il faudra
   traiter à part.

Point d'attention pour qui refera ces mesures : ne **jamais** re-scraper la
preview pour établir la vérité terrain. Les scrapers d'aujourd'hui ne
reproduisent plus les divergences historiques (`event_type` de Mesquer, doublon
Nozéen de #261) — un re-scrape effacerait précisément ce qu'on cherche à mesurer.

## Recommandations pour #289

1. **Implémenter R telle qu'écrite**, sans tolérance ni score. Le sur-outillage
   est ici le seul risque : les mesures montrent que toute souplesse ajoutée
   (millésime, suffixe de heat, ±j) fait passer les faux positifs de 0 à 37 ou 53
   sans rapprocher un seul vrai doublon de plus.
2. **Corriger #295 avant #289.** Sans lui, la `Course` survivante d'un heat
   effondré porte un `heat_slug` arbitraire et R sous-rapproche.
3. **Ne pas coder d'attente d'un rapprochement Klikego ↔ Breizh Chrono à
   l'import** : sur les cas mesurés (Mesquer, Nozéen), la clé d'identité **collide
   déjà**. Le chemin réellement emprunté par ces URLs est #283 (enregistrer une
   source passive), et le test de non-régression correspondant doit vérifier
   qu'**une seule** `Course` existe, avec **deux** sources.
4. **Le vrai bénéficiaire de R est l'inter-façade Breizh Chrono** (`live.` ↔
   `resultats.`), soit 2 identifiants sur les 59 du Sheet. C'est peu — mais c'est
   le seul endroit où l'automatisme apporte quelque chose que la clé d'identité ne
   fait pas déjà.
