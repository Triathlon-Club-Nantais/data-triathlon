# Feature Specification: Fan-out des heats Klikego / Breizh Chrono

**Feature Branch**: `feat/156-klikego-fanout-event`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: « Fan-out des heats Klikego : depuis une seule URL Klikego (ou Breizh Chrono, qui réutilise la même mécanique de heats), avec ou sans paramètre `?heat=`, importer toutes les épreuves de l'événement — pas seulement le premier heat détecté comme aujourd'hui. » (issue GitHub [#156](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/156))

## Vocabulaire (T1)

Trois termes cohabitent dans ce document et le code, cohérents avec `AGENTS.md` §Vocabulaire :

- **heat** : le slug côté chronométreur (`triathlon-s-indiv`, `swim-run-m-duo`, …). Concept d'énumération à la source.
- **épreuve** : la notion métier — une `source_url` unique. Un heat = une épreuve = une entrée dans la CLI.
- **Course** : l'entité en base (SQLAlchemy). Une épreuve = une `Course`. Unicité `(name, event_date, event_type)`.

Un fan-out Klikego = **N heats** → **N épreuves** → **N `Course`**, dans un seul import.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import complet d'un événement multi-épreuves (Priority: P1)

L'opérateur du club colle dans le formulaire d'ajout l'URL d'un événement Klikego (ou Breizh Chrono) qui regroupe plusieurs épreuves — par exemple un « Triathlon et Swimrun » composé d'un Triathlon S, d'un Swimrun et d'un relais. Peu importe que l'URL soit « nue » ou porte un `?heat=X` (copiée depuis la fiche d'un heat) : l'opérateur s'attend à ce que **toutes** les épreuves publiées de cet événement soient importées, apparaissent chacune comme une course distincte dans le catalogue, et que les participations correspondantes soient créées.

**Why this priority**: C'est le scénario nominal derrière l'issue #156. Aujourd'hui l'opérateur n'a aucun moyen depuis l'UI d'importer plus d'une épreuve par événement sans construire manuellement N URLs `?heat=…`. Sans cette histoire, la feature n'a pas de valeur.

**Independent Test**: Coller une URL d'événement multi-épreuves (nue ou avec `?heat=…`) dans `/ajouter` ; vérifier après import qu'autant de courses distinctes existent dans le catalogue que l'événement en publie, chacune avec ses participations, ses temps et son type (`triathlon-s`, `swimrun-s`, `duathlon`, etc.).

**Acceptance Scenarios**:

1. **Given** un événement Klikego qui publie 3 épreuves (triathlon S, swimrun S, relais), **When** l'opérateur colle l'URL nue de l'événement dans `/ajouter`, **Then** 3 courses distinctes sont créées, chacune identifiable par son type et son nom d'épreuve, avec l'intégralité de ses participations.
2. **Given** le même événement, **When** l'opérateur colle une URL portant `?heat=triathlon-s` (copiée depuis la fiche du heat), **Then** les 3 courses de l'événement sont créées à l'identique (le `?heat=` est ignoré, cf. A1).
3. **Given** l'URL nue d'un événement Breizh Chrono qui publie 2 heats, **When** l'opérateur colle l'URL, **Then** 2 courses distinctes sont créées avec la même mécanique.
4. **Given** un événement qui ne publie qu'**une seule** épreuve, **When** l'opérateur colle son URL, **Then** exactement 1 course est créée (le comportement dégénère proprement sur le mono-heat).

---

### User Story 2 - Ré-import d'un événement dont une nouvelle épreuve a été publiée (Priority: P2)

Un opérateur avait importé l'événement le mois dernier ; entre-temps, le chronométreur publie une épreuve supplémentaire (par exemple la remise du classement scratch corrigé, ou un heat « juniors » ajouté après coup). L'opérateur recolle la même URL nue de l'événement. Il s'attend à ce que la ou les nouvelles épreuves soient importées, et à ce que les épreuves déjà en base **ne** soient **pas** ré-importées inutilement (sauf si le cache est expiré, comme aujourd'hui).

**Why this priority**: Cas fréquent en cours de saison sur les gros événements. Sans ce comportement, l'opérateur aurait à mémoriser quels heats étaient déjà en base et à construire l'URL du seul heat manquant, ce qui rebâtit exactement le friction actuel.

**Independent Test**: Après l'US1, publier un nouveau heat côté source (ou simuler l'apparition), recoller la même URL nue, vérifier que seule la nouvelle course est effectivement re-scrapée et importée, et que les précédentes sont conservées telles quelles (indicateur : bilan d'import mentionnant « déjà en cache » pour les anciennes).

**Acceptance Scenarios**:

1. **Given** 3 courses déjà importées depuis un événement, **When** l'opérateur recolle l'URL nue et qu'une 4ᵉ épreuve est apparue à la source, **Then** l'import crée la 4ᵉ course et signale les 3 premières comme déjà en base / en cache.
2. **Given** 3 courses déjà importées et aucune nouvelle épreuve à la source, **When** l'opérateur recolle l'URL nue, **Then** l'import signale « rien de nouveau » sans réécrire les participations existantes.

---

### User Story 3 - Import en ligne de commande de masse (Sheet) avec URLs d'événement (Priority: P2)

L'administrateur exécute la commande d'import de masse depuis le tableur partagé du club, qui contient un mélange d'URLs — certaines avec `?heat=…`, d'autres nues. Il s'attend à ce que **toutes** les URLs Klikego / Breizh Chrono importent l'événement complet, indifféremment de la forme (A1) — cohérent avec l'UI. Les lignes qui pointaient historiquement sur un heat spécifique deviennent équivalentes à l'URL nue du même événement ; le cache TTL absorbe les doublons.

**Why this priority**: L'import de masse est la voie automatisée du club (batches périodiques). Le comportement doit être cohérent entre l'UI et la CLI, sans quoi le tableur se transforme en piège où le sens d'une ligne dépend de l'outil qui la lit.

**Independent Test**: Faire tourner l'import de masse en mode simulation (`--dry-run`) sur un tableur mélangé et vérifier que le décompte des épreuves à importer correspond bien à l'énumération réelle de chaque événement pour **toute** URL Klikego / Breizh Chrono, quelle que soit sa forme.

**Acceptance Scenarios**:

1. **Given** un tableur qui contient 5 URLs d'événements Klikego (2/3/1/4/2 épreuves respectivement, indépendamment de la présence ou non de `?heat=` sur chaque ligne), **When** l'administrateur lance l'import de masse en mode simulation, **Then** le bilan annonce 12 épreuves à importer.
2. **Given** un tableur qui contient une URL `?heat=triathlon-s` d'un événement à 3 heats, **When** l'import tourne, **Then** les 3 heats sont importés — le `?heat=` est ignoré (cf. A1). La ligne est équivalente à celle de la même URL nue ; le cache TTL évite tout re-scraping si le même événement est couvert par une autre ligne du Sheet.

---

### Edge Cases

- **Un heat de l'événement échoue au scraping, les autres réussissent** : le comportement attendu est que l'échec d'un heat n'empêche pas les autres d'être importés. Le bilan d'import doit lister le heat en erreur (URL + raison), les heats réussis restent en base.
- **Événement dont l'énumération des heats est vide** (page qui a perdu sa liste, ou événement pas encore publié) : l'import doit se comporter comme aujourd'hui pour une URL nue qui ne trouve rien (échec propre avec message qui nomme la cause), pas comme un import silencieusement vide qui laisserait croire que l'événement est chargé.
- **Heat listé côté source mais dont la page individuelle est vide** (annulé, reporté, classement pas encore publié) : le heat est signalé et sauté ; les autres heats de l'événement continuent.
- **Deux heats de l'événement portent un nom / une date / un type identiques** (jumeaux Klikego, cas rare) : la contrainte d'unicité en base empêche la double création — le second heat rentre en collision et est signalé, sans casser l'import des autres.
- **URL d'événement invalide** (identifiant erroné, événement retiré) : échec propre, pas de fan-out muet.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Quand l'opérateur soumet une URL Klikego **sans** paramètre de sélection d'épreuve (`?heat=`), le système MUST énumérer toutes les épreuves publiées de l'événement et importer chacune comme une course distincte.
- **Note de portée (Breizh Chrono, U2)** : Breizh Chrono est **hors scope V1**. Son fan-out est déjà implémenté (`breizhchrono.py:205-248` et `369-425`) et sa non-régression après refacto Klikego est couverte par la suite pytest complète (T036). Ce n'est pas un `FR` — c'est un rappel que la mécanique de heats existe sur deux providers, dont un seul est modifié ici.
- **FR-003**: Le fan-out MUST créer **une course par heat**, avec le type d'épreuve (triathlon-s / swimrun / etc.) correctement classifié pour chacun. Deux courses d'un même événement mais de types distincts doivent être différenciables dans le catalogue.
- **FR-004**: Le système MUST poursuivre l'import des autres heats quand un heat échoue au scraping. La liste des heats en échec MUST être exposée par le contrat SSE `done` et par le bilan CLI (texte + `--json`) avec, pour chaque heat, son identifiant et la cause. Format exact : cf. `contracts/klikego-fanout.md` §C4.
- **FR-005**: Quand l'opérateur recolle une URL déjà partiellement importée, le système MUST détecter les heats déjà en base et éviter de les re-scraper inutilement, en s'appuyant sur les mêmes règles de cache que celles utilisées aujourd'hui pour un heat unique.
- **FR-006**: Le paramètre `?heat=X` **éventuellement présent** dans une URL soumise depuis l'UI ou l'import de masse (Sheet) MUST être **ignoré** — le contrat est « URL Klikego / Breizh Chrono = événement entier », sans distinction entre URL nue et URL avec heat, et sans distinction entre le chemin UI et le chemin CLI (`import-sheet`). Cela facilite l'expérience utilisateur (l'opérateur qui copie une URL depuis une fiche épreuve arrive avec `?heat=` et n'a pas à le retirer) et rend le sens d'une ligne de Sheet indépendant de la forme de l'URL et de l'outil qui la lit.
- **FR-007a**: Une **échappatoire explicite** MUST exister côté ligne de commande pour importer volontairement un heat unique, afin de couvrir les cas de bord (heat cassé à la source, embargo, faux positif TCN). Le nom exact du drapeau est laissé au plan technique ; il MUST être documenté et distinct du chemin nominal (pas activable par la seule forme d'URL, sans quoi le contrat FR-006 est réintroduit par la porte dérobée).
- **FR-008**: Le bilan d'import MUST rester lisible dans le cas fan-out. Les compteurs suivants MUST être disponibles côté SSE `done` **et** côté bilan CLI (texte + `--json`) :
    - `heats_enumerated` — nombre de heats trouvés à la source
    - `heats_imported` — nombre de heats effectivement scrapés (frais)
    - `heats_cached` — nombre de heats servis depuis le cache TTL
    - `heats_failed` — nombre de heats qui ont levé pendant leur scrape
    - `failures` — liste `[{heat_slug, reason}]` des heats en échec
  Sur un import mono-heat (échappatoire `--single-heat` ou provider non-Klikego qui ne fan-oute pas), les 4 compteurs valent 0 ou 1 sans branche conditionnelle côté consommateur.
- **FR-009**: Après un import via l'UI, la navigation post-import MUST rester cohérente — cf. Q2 ci-dessous. L'assumption par défaut est de rester sur `/ajouter` en affichant un récapitulatif listant les N courses créées avec un lien vers chacune, plutôt que d'imposer une redirection unique quand N > 1.
- **FR-010**: L'énumération des heats d'un événement MUST lire la **liste canonique** de la source (le `<el-select name="heat">` du HTML de la page événement, cf. `contracts/klikego-fanout.md` §C1). Deux comportements attendus, à l'exclusion de tout autre :
  1. `<el-select>` présent → tous les heats publiés sont retournés dans l'ordre du DOM.
  2. `<el-select>` absent → liste vide retournée ; `import_service._require_event_name` produit alors l'erreur nominale « nom d'épreuve introuvable ».
  Un heat manqué alors qu'il est présent dans le `<el-select>` est un bug (test `test_enumerate_heats_mesquer` doit lever si régression).

### Key Entities

- **Événement** : entité amont regroupant plusieurs épreuves publiées par un même chronométreur (Klikego ou Breizh Chrono), désignée par une URL nue. Un événement porte un nom, une date, et une liste de heats. Il n'a **pas** d'existence propre dans le catalogue interne ; il ne sert qu'à l'énumération à l'import.
- **Heat** : une épreuve individuelle publiée à l'intérieur d'un événement (triathlon-s, swimrun, relais…). Chaque heat aboutit à **une** course dans le catalogue. Un heat porte un identifiant textuel (`triathlon-s-indiv`, `swimrun-…`), un type d'épreuve classifié, et une liste de participations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Depuis une URL d'événement multi-épreuves collée dans l'UI d'ajout, l'opérateur récupère **100 %** des heats publiés en une seule action, contre 1 seul heat aujourd'hui.
- **SC-002**: L'opérateur du club n'a **plus besoin de construire manuellement d'URLs `?heat=…`** pour importer plusieurs épreuves d'un même événement (métrique de friction : nombre de collages successifs pour importer un événement 3-heats passe de 3 à 1).
- **SC-003**: L'import de masse depuis le tableur partagé traite toute URL Klikego / Breizh Chrono comme « événement entier », quelle que soit la forme (nue ou `?heat=…`) — cohérent avec l'UI.
- **SC-004**: Un heat qui échoue au scraping **n'empêche pas** l'import des autres heats de l'événement. Sur un événement 3-heats dont 1 est en erreur : 2 courses sont créées, le SSE `done` porte `heats_failed=1` et `failures=[{heat_slug, reason}]`, le bilan CLI liste l'échec sous « Heats en erreur (détail) : » (parité avec `Épreuves en erreur (détail)` existant).
- **SC-005**: Sur un ré-import d'un événement dont N heats sont déjà en cache et K heats nouveaux, le nombre de requêtes de scraping HTTP est proportionnel à K, pas à N + K. Exemple chiffré : Mesquer 8 heats, 3 en cache, 5 nouveaux → 5 fetches de détail, pas 8 (verrouillé par T008a, T013 et T023 qui comptent les appels au scraper de heat).

## Assumptions

- **`Course.source_url` reste au niveau du heat**, pas de l'événement : chaque course créée par le fan-out porte comme `source_url` l'URL complète du heat (`…?heat=X`), pas l'URL nue de l'événement qui a servi à l'énumération. C'est cette clé qui pilote aujourd'hui le cache TTL et le rejeu ciblé (`rescrape-db --url …`), et rien ne motive son changement.
- **L'URL d'événement collée par l'opérateur n'est pas persistée comme clé de cache** ; deux imports successifs de la même URL nue ré-énumèrent les heats, mais les heats individuels sont retrouvés en cache par leur propre `source_url` — donc le coût du ré-import est marginal.
- **L'énumération des heats se fait à la source, pas depuis la base** : l'objectif est bien de découvrir les épreuves publiées côté chronométreur, pas de re-lister celles déjà importées. Un heat retiré côté source n'est pas énuméré ; les courses déjà en base pour ce heat retiré ne sont pas touchées.
- **Le classement des heats détectés n'est pas ordonnancé** (Klikego et Breizh Chrono ne publient pas de rang canonique entre heats). L'ordre d'import n'est pas garanti, mais le bilan les liste de façon stable (par exemple par identifiant de heat lexicographique).
- **Breizh Chrono est HORS scope de la V1** : le sondage 2026-07-31 (`docs/superpowers/specs/2026-07-31-klikego-fanout-sondage.md`) a établi en lisant le code que `breizhchrono.py:205-248` (`resultats.breizhchrono.com` / `www.breizhchrono.com`) et `breizhchrono.py:369-425` (`live.breizhchrono.com`) **bouclent déjà** sur tous les heats via `_fetch_all_heats` / `_parse_live_heats` quand aucun `?heat=` n'est fourni. Le fan-out ne concerne donc que **Klikego**. Contrat côté opérateur : conforme à A1, aucune régression Breizh Chrono attendue.
- **Les autres chronométreurs qui exposent déjà une URL d'événement importée d'un coup** (Chronoplace, ok-time, RaceResult…) sont **hors périmètre** : ils gèrent déjà l'événement entier en un appel et n'ont pas de notion de heat à énumérer.
- **Aucune migration de données** : les courses déjà en base restent inchangées, seul le comportement d'import à partir d'une URL nue change.

## Arbitrages retenus

Les trois points structurants ont été tranchés avec le porteur avant `/speckit-plan`. Ils sont figés ici pour éviter tout retour en arrière silencieux au plan.

### A1 (Q1) — URL Klikego/Breizh Chrono = événement entier, `?heat=` ignoré

**Contexte** : le formulaire d'ajout et le tableur du club acceptent aujourd'hui indifféremment des URLs nues et des URLs `?heat=X`.

**Décision** : URL Klikego/Breizh Chrono = **événement entier**, avec ou sans `?heat=X`. L'expérience utilisateur prime : l'opérateur qui copie une URL depuis la fiche d'une épreuve arrive naturellement avec `?heat=X`, et le fait de retirer ce paramètre n'a aucun sens métier. Une seule règle : URL Klikego = tous les heats. Traduit dans FR-006.

**Contre-partie** : les cas de bord (importer volontairement un heat unique — source cassée, embargo, faux positif TCN) demandent une échappatoire explicite, non basée sur la forme d'URL — cf. A3/FR-007a.

### A2 (Q2) — Récap sur `/ajouter` quand N courses sont créées

**Contexte** : depuis PR #144, la fin d'un import réussi redirige l'opérateur vers `/courses/<id>`. Cette redirection suppose **une** course cible.

**Décision** : rester sur `/ajouter` avec un récapitulatif listant les N courses créées et un lien vers chacune. Le récap doit être lisible pour le cas N=1 aussi (pas de branche UI conditionnelle qui ferait perdre l'info « il y avait 1 course » quand N=1). Traduit dans FR-009.

### A4 — Volume assumé, pas de filtrage

**Contexte** : le sondage `docs/superpowers/specs/2026-07-31-klikego-fanout-sondage.md` établit qu'après fan-out, le Sheet actuel ferait passer la base de ~43 à ~241 courses Klikego (facteur ×5,6, +198 heats), avec une majorité de heats jeunes / kids / meta (aquathlon 2013-2014, demi-finales régionales, challenges agrégés).

**Décision** : livrer tel quel. Aucun filtre à l'import — la spec **n'ajoute pas** de critère « seulement les heats avec ≥1 participant TCN » ni de motif d'exclusion par nom. Le catalogue absorbe le volume ; un nettoyage manuel post-merge sera fait au cas par cas si besoin, en dehors de la feature.

**Conséquences prises en compte** : les vues qui listent les épreuves (dashboard, page club, filtres) doivent rester lisibles avec ~200 courses supplémentaires. Le porteur assume l'impact sur les affichages, à voir sur données réelles.

### A3 (Q3) — Échappatoire CLI pour importer un heat unique

**Contexte** : puisqu'A1 supprime toute possibilité d'importer un seul heat via l'URL, il faut un mécanisme explicite pour les cas de bord.

**Décision** : un drapeau CLI (nom exact à décider au plan, `--single-heat` étant un candidat naturel) permet de forcer l'import d'un heat unique en ligne de commande. **Chemin exceptionnel**, distinct du chemin nominal : pas activable par la forme d'URL, pas exposé dans le tableur ni dans l'UI /ajouter — sans quoi on réintroduit par la porte dérobée l'ambiguïté qu'A1 a levée.

**À vérifier au sondage** (prérequis à `/speckit-plan`) : combien d'événements du Sheet actuel comportent des heats non déclarés jusqu'ici (donc absents de la base après le premier import fan-out), pour savoir si une action de curation manuelle est à prévoir post-merge.
