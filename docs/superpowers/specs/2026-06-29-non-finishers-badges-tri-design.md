# Non-finishers : badges & tri en fin de tableau — Design

**Date :** 2026-06-29
**Contexte :** issue #11 (import exhaustif Klikego/BC). Depuis que l'import remonte
l'épreuve complète (finishers + DNF/DNS/DSQ) via le data block, les non-finishers
apparaissent mêlés aux classés. Deux problèmes observés sur le 6e Duathlon Nozeen
(heat `duathlon-s---open`) :

1. Deux athlètes TCN **DNS** (CHAUVET Romain, GORET Antoine, dossards 114/136)
   s'affichent avec un **rang 0** et un **temps `00:00:00`**, et remontent en tête
   du tableau au lieu d'être relégués.
2. Aucun marquage visuel ne distingue un non-finisher d'un finisher dans le
   tableau `RaceFinishers`.

## Cause racine du symptôme « rang 0 / 00:00:00 »

Le data block donne ces athlètes correctement : `status=DNS`, rang vide, temps vide.
`parse_data_row` les neutralise comme attendu. Mais comme ils sont TCN, la **Phase C**
de `klikego.scrape_event_all` interroge leur page détail
(`resultat-participant.jsp`) pour enrichir les splits fins. Cette page renvoie un
**placeholder** `Temps Officiel 00:00:00` et un rang `0` pour un non-partant.
`_parse_detail` (klikego.py:90-106) lit ces valeurs et écrase :

- `total_time = ""` → `"00:00:00"` ;
- `rank_overall = None` → `0`.

Le `status` reste `DNS`, mais le faux rang `0` fait remonter la ligne en tête au tri
par rang, et le faux temps s'affiche.

## Objectifs

- DNF, DNS, DSQ distingués des finishers par un **badge** dans le tableau.
- Non-finishers **relégués en fin** de tableau, après les finishers classés.
- **DNF/DSQ peuvent porter un temps** (course entamée puis abandon / disqualification) ;
  **DNS n'a jamais de temps**.
- Corriger la cause racine : ne plus fabriquer de faux rang `0` / temps `00:00:00`.

## Non-objectifs (YAGNI)

- Pas de refonte du `Leaderboard` (qui gère déjà `StatusBadge` + tri par rang).
- Pas de nouvelle colonne ni de nouveau statut.
- Pas de changement de modèle DB / migration (le champ `status` existe déjà et
  circule jusqu'au frontend).

---

## Volet A — Backend

### A1. `parse_data_row` (`app/scrapers/klikego_platform.py`) — préserver le temps des DNF/DSQ

Comportement actuel : `total_time` est neutralisé (`""`) pour **tout** statut non vide.

Nouveau comportement :

- `rank_overall` / `rank_category` → `None` pour tout non-finisher (jamais classés).
- `total_time` :
  - **DNF** et **DSQ** → conservé depuis le champ `officiel` (normalisé), s'il existe ;
  - **DNS** → forcé `""` (un non-partant n'a par définition aucun temps).

### A2. `_parse_detail` (`app/scrapers/klikego.py:90-106`) — ignorer les placeholders

Garde-fous valables pour tous (un `00:00:00` officiel ou un rang `0` ne sont jamais
des valeurs réelles) :

- ne pas écraser `total_time` si la valeur normalisée vaut `00:00:00` ;
- ne pas poser `rank_overall` (ni `rank_category` / `rank_gender`) à partir d'un rang `0`.

C'est la correction de cause racine du symptôme CHAUVET/GORET. Elle protège aussi les
athlètes non-TCN au cas où ils passeraient un jour par la page détail.

---

## Volet B — Frontend (`frontend/components/results/RaceFinishers.tsx`)

Le composant reçoit déjà `status` (exposé par `ParticipationOut`, présent dans le type
`Participation`) mais ne l'exploite pas.

### B1. Tri

Ordre appliqué dans le composant avant rendu :

1. **Finishers** (`status === "finisher"` ou statut vide) d'abord, par `rank_overall`
   croissant (les `null` après).
2. **Non-finishers** ensuite, **groupés par statut** dans l'ordre **DNF → DSQ → DNS** :
   - au sein de **DNF** et **DSQ** : par temps croissant (lignes sans temps en fin de
     groupe), puis par nom alphabétique ;
   - **DNS** : par nom alphabétique.

### B2. Colonne « Rang »

Pour un non-finisher, remplacer le `PlaceBadge` par le `StatusBadge` existant
(`frontend/components/results/StatusBadge.tsx`) : sigle DNS/DNF/DSQ, variante
`destructive`, tooltip « Abandon » / « Non partant » / « Disqualifié ».

### B3. Colonne « Temps total »

Inchangée : affiche le temps si présent (DNF/DSQ peuvent en avoir un), sinon `—`
(cas DNS).

### B4. Filet visuel

Une ligne non-finisher reçoit un fond très légèrement grisé (token `--tcn-grey`
léger) pour la détacher du peloton classé, sans casser le liseré orange TCN.

---

## Tests

### Backend (`tests/test_klikego.py`)

- `parse_data_row` :
  - DNF avec `officiel` rempli → `total_time` conservé, `rank_overall is None` ;
  - DSQ avec `officiel` rempli → `total_time` conservé, `rank_overall is None` ;
  - DNS → `total_time == ""`, `rank_overall is None`.
- `_parse_detail` : sur une page détail renvoyant `Temps Officiel 00:00:00` et rang
  `0`, le résultat ne doit pas voir `total_time` ni `rank_overall` modifiés (restent
  vides/`None`).

### Frontend (`frontend/components/results/RaceFinishers.test.tsx`)

- Un DNS sans temps est rendu **après** les finishers, avec badge « DNS » dans la
  colonne rang et `—` en temps total.
- Un DNF avec temps est rendu après les finishers, badge « DNF », temps affiché.
- L'ordre des groupes DNF → DSQ → DNS est respecté.

---

## Fichiers touchés

- `backend/app/scrapers/klikego_platform.py` — A1 (`parse_data_row`).
- `backend/app/scrapers/klikego.py` — A2 (`_parse_detail`).
- `backend/tests/test_klikego.py` — tests A1/A2.
- `frontend/components/results/RaceFinishers.tsx` — B1-B4.
- `frontend/components/results/RaceFinishers.test.tsx` — tests B.
