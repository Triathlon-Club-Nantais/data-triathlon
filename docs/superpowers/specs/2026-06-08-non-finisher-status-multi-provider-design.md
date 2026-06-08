# Statuts DNS / DNF / DSQ — extension aux providers restants — design (2026-06-08)

> **Implémenté** (2026-06-08) : commits `94d3202` (helper partagé),
> `dc485b5`+`353409d` (TimePulse), `4268db0`+`f3e8d96` (Wiclax), `724df31`
> (Klikego), `af489b1` (Breizh par héritage), `b63b5eb` (Sport Innovation),
> `15cf6e0` (tests d'intégration). 209 tests unitaires verts.
>
> **Découvertes (réseau réel)** ayant ajusté les emplacements candidats du plan :
> - **TimePulse** : non-partant encodé par le flag binaire `np="1"` sur `<E>`
>   (→ DNS), pas par un attribut texte. Fix structurel : les `<E>` sans `<R>`
>   sont désormais conservés.
> - **Wiclax** : `np="1"` sur `<E>` (→ DNS) + libellé dans l'attribut temps `t`
>   du `<R>` (`t="Abandon"`→DNF, `t="Disqualifié"`→DSQ). Correctif annexe : la
>   ré-population du rang depuis `v` est gardée pour ne pas ressusciter un rang purgé.
> - **Sport Innovation** : aucun champ de statut dans l'API (les non-finishers
>   sont simplement omis) ni de libellé dans le HTML aujourd'hui → l'extraction
>   est défensive (no-op tant que le payload n'expose pas de statut).

> **Suite de** `2026-06-08-dns-dnf-handling-design.md` (prolivesport + infra,
> déjà implémenté : commits `9a30c0e`, `574cd5f`, `85fc221`, `f16a11c`).
> Ce spec couvre **les 5 providers restants** explicitement exclus du premier.

## Problème

Le premier chantier a fiabilisé le statut pour **prolivesport** uniquement.
Les autres providers restent au comportement « hérité » :

- L'infra (`mapping.derive_status`) ne sait dériver que `finisher` / `DNF` par
  heuristique sur la présence d'un temps total → **impossible de distinguer
  DSQ vs DNS vs DNF**.
- **TimePulse** *jette* les athlètes sans balise `<R>` (`timepulse.py:271`,
  `continue`) → un abandon/non-partant **disparaît** de l'import. (Confirmé par
  l'audit `2026-06-08-scrapers-audit-report.md` : 100 % de temps = seuls les
  finishers sont remontés.)
- **Wiclax** *conserve* déjà ses non-finishers (audit : 12 % sans temps =
  DNF/DNS) mais sans statut explicite → tous étiquetés `DNF` par l'heuristique.
- **Klikego/Breizh** et **Sport Innovation** : statut explicite jamais lu.

On veut **savoir** qu'un membre du club est DNF/DNS/DSQ, sans introduire de
faux positifs.

## Décisions de cadrage (validées avec @tjarrier)

1. **Cible : backend-v2 uniquement** (v1 déprécié, cf. AGENTS.md).
2. **Providers couverts :** Klikego (+ Breizh Chrono par héritage), TimePulse,
   Wiclax/G-Live, Sport Innovation.
3. **Conserver les non-finishers partout** — notamment corriger le drop
   TimePulse, comme fait pour prolivesport.
4. **Statut précis seulement si le provider l'expose explicitement.** Sinon
   `status=""` → on garde l'heuristique actuelle (`finisher` si temps total,
   sinon `DNF`). Approche conservatrice : zéro faux positif.

## Périmètre

**Inclus :**
- Helper partagé de reconnaissance de label dans `app/scrapers/utils.py`.
- Extraction du label/champ de statut brut dans chaque provider concerné.
- Fix TimePulse : ne plus jeter les athlètes sans `<R>`.
- Tests unitaires (fixtures synthétiques) + intégration (réseau réel).

**Exclus :**
- Pas de nouvelle migration Alembic — la colonne `Participation.status` existe
  déjà (`e4211f35a275_initial_schema.py`).
- `mapping.derive_status` **inchangé** (déjà conforme : respecte `status`
  explicite, sinon heuristique).
- Pas de front (frontend-v2 pas encore codé).
- Pas de distinction stats finishers/non-finishers (`stats_service` inchangé).
- prolivesport (déjà traité).

## Vocabulaire des statuts

Réutilise les constantes existantes de `app/scrapers/base.py` :
`STATUS_FINISHER` (`"finisher"`), `STATUS_DNF` (`"DNF"`), `STATUS_DNS`
(`"DNS"`), `STATUS_DSQ` (`"DSQ"`). Aucune nouvelle valeur (pas de bucket
« non-finisher » générique : choix « précis si explicite »).

## 1. Helper partagé — `app/scrapers/utils.py`

Nouveau : `derive_status_from_label(label: str) -> str`.

- Normalise un label textuel brut (trim, casse, accents/ponctuation) et renvoie
  l'une des constantes `STATUS_*`, ou `""` si non reconnu.
- Tables de jetons reconnus (FR/EN), à compléter à la lumière des données
  réelles (cf. §4 Découverte) :
  - **DSQ** : `dsq`, `disq`, `disqualifie`, `disqualified`.
  - **DNF** : `dnf`, `abd`, `abandon`, `ab`.
  - **DNS** : `dns`, `non partant`, `np`, `forfait`, `ff`.
  - **finisher** : `finisher`, `classe`, `fin`, `ok` *(seulement si un provider
    pose un label positif explicite ; sinon on ne s'en sert pas)*.
- Importe les constantes depuis `base.py` (couche la plus basse, déjà importée
  par les scrapers).
- **`""` (non reconnu) est le défaut sûr** → l'heuristique de `mapping`
  s'applique, comportement identique à aujourd'hui.

Rationale : factorise la table de labels (l'AGENTS.md demande de ne pas
dupliquer la logique cross-provider, cf. Breizh↔Klikego).

## 2. Fix structurel TimePulse — `app/scrapers/timepulse.py`

Actuellement (`~ligne 270`) :

```python
r_tag = _find_tag(xml, "R", "d", bib)
if not r_tag:
    continue  # no result for this athlete (DNS/DNF)
```

→ **Ne plus `continue`.** Créer le `ScrapedResult` même sans `<R>` :

- Identité/club/catégorie/genre proviennent du `<E>` (déjà parsé avant).
- Pas de `<R>` → `total_time=""`, splits vides, rangs `None`.
- `status` : posé via `derive_status_from_label(...)` si le `<E>`/`<R>` porte un
  attribut de statut explicite (à identifier, §4) ; sinon `""` → heuristique
  (`DNF`).
- Quand `<R>` existe : comportement actuel inchangé, plus lecture éventuelle
  d'un attribut de statut explicite.

## 3. Extraction du statut par provider

Pour chaque provider, **n'écrire `result.status` que si un marqueur explicite
est trouvé** ; sinon laisser `""`.

- **Klikego** (`klikego.py`, via `_parse_detail` et/ou le listing) — lire le
  label de statut s'il existe (colonne « Clt »/« Statut » ou mention
  « Abandon »/« NC »). **Breizh Chrono en hérite** (réutilise la logique
  Klikego — ne pas dupliquer).
- **Wiclax** (`wiclax.py`) — lire un éventuel attribut de statut du `<R>`/listing.
  À défaut de marqueur : les 12 % sans temps restent `DNF` par heuristique
  (comportement déjà en place, on ne régresse pas).
- **Sport Innovation** (`sportinnovation.py`) — lire le statut de la ligne/JSON
  (formes HTML *et* `results.sportinnovation.fr/race/{slug}`).

Pour un non-finisher détecté explicitement, appliquer la même hygiène que
prolivesport : `total_time=""`, rangs `None` (éviter les temps/rangs bidons).

## 4. Étape de découverte (par provider, AVANT le code de détection)

Le **nom exact du champ/label de statut** dans chaque payload réel est inconnu.
Première tâche de chaque provider :

1. Récupérer une épreuve réelle contenant un non-finisher (réutiliser
   `scripts/audit_scrapers.py` / URLs de référence @tjarrier).
2. Inspecter le payload (HTML/XML/JSON) pour identifier le porteur du statut :
   attribut, colonne, ou simple absence de temps.
3. En déduire les jetons à ajouter à `derive_status_from_label` et le point
   d'extraction dans le scraper.

Si un provider **n'expose aucun marqueur explicite**, on s'arrête à « conserver
le participant » (statut heuristique) — conforme au choix de cadrage.

## 5. Tests (TDD)

### Unitaires (sans réseau)

- `tests/test_scrapers_utils.py` (ou existant) — table de
  `derive_status_from_label` : DSQ/DNF/DNS reconnus (FR+EN), label inconnu → `""`,
  vide → `""`.
- `tests/test_timepulse.py` — un `<E>` **sans** `<R>` est désormais **conservé**
  (`total_time==""`, rangs `None`, statut heuristique `DNF` ou explicite).
- `tests/test_klikego.py`, `tests/test_wiclax.py`,
  `tests/test_sportinnovation.py`, `tests/test_breizhchrono.py` — quand le
  fixture porte un label explicite, `result.status` est correct ; sans label,
  `result.status == ""`.

### Intégration (`pytest -m integration`)

- `tests/test_integration_scrapers.py` — pour chaque provider disposant d'une
  épreuve de référence avec non-finisher : l'import renvoie au moins un
  `status != "finisher"` **et** au moins un `finisher`. (Best-effort : si aucune
  épreuve de référence ne contient de non-finisher identifiable, documenter et
  se limiter à « le participant est conservé ».)

## Compatibilité & risques

- **Pas de régression** : `status=""` par défaut → heuristique identique à
  aujourd'hui pour tout cas non reconnu.
- **Volume d'import** : conserver les non-finishers augmente le nombre de
  participations. Le filtre club (TCN) reste appliqué côté import → on ne
  conserve que les non-finishers pertinents pour le club.
- **Doublons** : `UNIQUE(course_id, bib_number)` inchangé ; un non-finisher a un
  dossard → pas de collision nouvelle. (TimePulse : vérifier qu'un `<E>` sans
  `<R>` a bien un `bib` non vide — déjà filtré ligne 266.)
- **Limite assumée** : sans marqueur explicite, DNS et DNF ne sont pas
  distinguables → l'heuristique étiquette `DNF`. Compromis du choix « précis si
  explicite ».
- **Découverte = inconnue clé** : si un provider encode le statut d'une façon
  imprévue, la détection précise est reportée (le participant reste néanmoins
  conservé). Le plan isolera la découverte de chaque provider en tâche distincte.
