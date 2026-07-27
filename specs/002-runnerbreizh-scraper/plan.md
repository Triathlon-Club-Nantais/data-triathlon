# Implementation Plan: Support de runnerbreizh.fr comme fournisseur de résultats

**Branch**: `tjarrier/feat-scrapers-supporter-runnerbreizh.fr-html-sta` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-runnerbreizh-scraper/spec.md`
**Ground truth**: `docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md`

## Summary

Ajouter un dixième provider, `app/scrapers/runnerbreizh.py`, exposant
`scrape_event_all(url)` et enregistré dans `registry.PROVIDERS` via
`HostMatchedProvider` sur `runnerbreizh.fr`.

Approche technique : canonicaliser l'URL d'entrée (ne garder que
`CourseFichierGpsNom`), lire les métadonnées de l'épreuve dans le `<title>`, puis
boucler `&page=N` en parsant `table.tableau-courses` avec BeautifulSoup jusqu'à
la première page sans ligne de résultat. Chaque ligne produit un `ScrapedResult`
dont les colonnes 2/3/5 alimentent les slots positionnels `swim_time` /
`bike_time` / `run_time` — `services.mapping.build_splits` les ré-étiquette selon
la discipline. Aucun changement de modèle, aucune migration, aucun changement
d'API : le provider s'insère dans une chaîne d'import inchangée.

## Technical Context

**Language/Version**: Python 3.13 (backend, `uv`)

**Primary Dependencies**: `httpx` (client HTTP sync), `beautifulsoup4` + `lxml`
(parsing). Aucune dépendance nouvelle — Playwright n'est **pas** nécessaire, le
site est statique.

**Storage**: PostgreSQL (prod, Supabase) / SQLite (dev). Modèle inchangé
(`Athlete`, `Course`, `Participation`).

**Testing**: pytest. Tests unitaires **sans réseau** (fixtures HTML réduites +
monkeypatch de `httpx.Client`, convention de `tests/test_t2area.py`) ; accès réel
derrière le marker `integration` dans `tests/test_integration_scrapers.py`.

**Target Platform**: Linux (backend Render, dev local)

**Project Type**: web service (backend FastAPI + frontend Next.js) — cette feature
est **backend seul**, aucun changement front.

**Performance Goals**: `ceil(classés / 50) + 1` requêtes HTTP par épreuve, aucune
requête par participant. Pire cas du panel : 8 requêtes pour 356 classés. Pire cas
théorique du site : le 70.3 des Sables (2704 classés) → 56 requêtes.

**Constraints**: pas de session ni de cookie requis ; pas de JavaScript ; la
structure HTML observée (8 colonnes) est le contrat de parsing et doit être
vérifiée, non supposée — une page hors format doit dégrader (ligne ignorée ou
erreur explicite), jamais produire une donnée fausse.

**Scale/Scope**: 1 module de scraper (~350-400 lignes avec docstrings), 1 ligne
dans le registre, ~25-40 tests unitaires, 9 fixtures HTML réduites, 1-2 tests
d'intégration. 10 liens du Sheet débloqués (4 épreuves distinctes).

## Constitution Check

*GATE: passé avant Phase 0, re-vérifié après Phase 1.*

Le template ne contient qu'un placeholder pour cette section (TODO connu du Sync
Impact Report de la constitution). La grille est donc explicitée ici, principe par
principe, comme l'exige la Gouvernance.

| Principe | Verdict | Justification |
| --- | --- | --- |
| **I. Langue** | ✅ Conforme | Arbitré en clarification : docstrings et commentaires techniques du nouveau module en **anglais**, vocabulaire métier et messages d'erreur destinés à l'opérateur (`raise ValueError("…")`, ré-affichés verbatim par le front) en **français**. Aucun fichier existant réécrit (règle de transition). `spec.md`, `plan.md` et le sondage restent en français (documents produit). |
| **II. Architecture en couches** | ✅ Conforme | Le scraper est en bas de la chaîne : il ne connaît ni `Session`, ni repository, ni service. Il ne touche pas `core/club.py` — et n'a rien à en réimplémenter, puisque le site ne publie aucun club (contrairement à T2Area, qui doit filtrer par club et **importe** `is_tcn`). |
| **III. TDD sans réseau** | ✅ Conforme, structurant | Chaque tâche d'implémentation part d'un test rouge sur fixture. Le réseau réel est isolé derrière `integration`. Les fixtures sont des extraits réels réduits, capturés le 27/07/2026. |
| **IV. Contrats API et CLI** | ✅ Conforme | Aucun changement de contrat : ni endpoint, ni paramètre, ni code de sortie. Le provider s'ajoute derrière `detect_provider`, la CLI le voit comme les neuf autres (y compris `--provider runnerbreizh` pour `rescrape-db`, via le nom déclaré). |
| **V. Neutralité des paramètres transverses** | ✅ Sans objet | Aucun paramètre de lecture ajouté ou modifié. |
| **VI. Simplicité / YAGNI** | ✅ Conforme, sous surveillance | Le module réutilise l'outillage existant (`utils.split_athlete_name`, `classify.classify_event_type`, `mapping.build_splits`, la déduplication sans dossard de `import_service`) plutôt que de le réécrire. Un seul point de vigilance : ne **pas** factoriser prématurément le parsing de cellule avec les autres scrapers HTML — la note de `registry.py` l'interdit explicitement tant que les signatures divergent. |

**Contraintes additionnelles** : stack respectée (aucune dépendance nouvelle) ;
aucune modification de schéma donc **aucune migration Alembic** ; temps conservés
en strings normalisées via `scrapers/utils.py` ; cache TTL inchangé, le provider
ne le court-circuite pas.

**Violations à justifier** : aucune. La section Complexity Tracking est donc vide
et supprimée.

## Project Structure

### Documentation (this feature)

```text
specs/002-runnerbreizh-scraper/
├── spec.md              # Spécification (avec Clarifications)
├── plan.md              # Ce fichier
├── research.md          # Décisions techniques et alternatives écartées
├── data-model.md        # Correspondance colonnes du site → champs du modèle
├── quickstart.md        # Vérification manuelle de bout en bout
├── contracts/
│   └── provider-contract.md   # Contrat ScraperProtocol respecté par le module
├── checklists/
│   └── requirements.md  # Checklist qualité de la spec
└── tasks.md             # Produit par /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── scrapers/
│       ├── runnerbreizh.py        # NOUVEAU — le provider
│       └── registry.py            # MODIFIÉ — import + entrée dans PROVIDERS
└── tests/
    ├── test_runnerbreizh.py       # NOUVEAU — tests unitaires sans réseau
    ├── test_registry.py           # MODIFIÉ — détection par host, non-régression SSRF
    ├── test_integration_scrapers.py  # MODIFIÉ — 1 test réseau réel (marker integration)
    └── fixtures/
        ├── runnerbreizh_page1_triathlon.html   # NOUVEAU — 3 lignes + en-tête + bandeau
        ├── runnerbreizh_page2_derniere.html    # NOUVEAU — dernière page partielle
        ├── runnerbreizh_page_vide.html         # NOUVEAU — au delà de la dernière page
        ├── runnerbreizh_page_introuvable.html  # NOUVEAU — titre vide, identifiant inconnu
        ├── runnerbreizh_duathlon.html          # NOUVEAU — colonnes trompeuses
        ├── runnerbreizh_aquathlon.html         # NOUVEAU — colonne vélo vide
        ├── runnerbreizh_duo.html               # NOUVEAU — relais, rangs partagés
        ├── runnerbreizh_lignes_anomales.html   # NOUVEAU — anonymes, nom mutilé, hors format
        └── runnerbreizh_republication.html     # NOUVEAU — mention « Chronométrée par »

docs/superpowers/specs/
└── 2026-07-27-runnerbreizh-sondage.md   # DÉJÀ ÉCRIT — vérité de terrain

AGENTS.md                                 # MODIFIÉ — provider et ses limites
```

**Structure Decision**: aucune structure nouvelle. Le projet a une convention
établie « un module par provider dans `app/scrapers/`, un fichier de tests par
provider, fixtures réduites dans `tests/fixtures/` » suivie par les neuf
providers existants ; on s'y conforme strictement.

## Conception du module

### Ossature (ordre de lecture = ordre du flux)

```text
_HOSTS / PROVIDER_NAME                  constantes
canonical_url(url)          →  str      ne garde que CourseFichierGpsNom, force page absente
_page_url(base, page)       →  str      ajoute &page=N
_fetch(client, url)         →  str      GET + raise_for_status, ScraperError sur échec réseau
_parse_title(html)          →  EventMeta  nom nettoyé, date, ville, km, discipline annoncée
_result_rows(html)          →  list[Tag]  lignes de données de table.tableau-courses
_parse_row(row, meta, url)  →  ScrapedResult | None
_parse_segment_cell(cell)   →  SegmentCell (temps, rang, écart %, vitesse)
scrape_event_all(url)       →  list[ScrapedResult]   boucle de pagination
```

### Décisions de conception

1. **Canonicalisation de l'URL** — on **reconstruit** la query à partir du seul
   `CourseFichierGpsNom` plutôt que de retirer `page`/`tricourse`/`Sexe` par
   soustraction : une allowlist est stable si le site ajoute demain un quatrième
   paramètre de vue. `source_url` transmis au mapping est l'URL canonique, donc
   deux formes du Sheet convergent sur **une** clé de cache TTL.

2. **Refus de la fiche coureur** — `triathlons.php?CoureurNom=…` porte le même
   host, donc `matches()` est vrai et l'URL arrive dans `scrape_event_all`. Le
   refus se fait là, sur l'absence de `CourseFichierGpsNom` (test sur le
   paramètre, pas sur le chemin : il couvre aussi toute autre page du site), par
   un **`ValueError` au message en français** nommant la forme attendue — la
   convention des neuf providers existants (`t2area`, `breizhchrono`). C'est
   `import_service._scrape_all` qui le convertit en `ProviderNotSupportedError`,
   dont le message est sérialisé verbatim vers le front (422) et vers le détail
   des échecs de la CLI. Le module ne lève **pas** de `DomainError` lui-même : il
   ne connaît pas les couches au-dessus (principe II).

3. **Épreuve introuvable** — identifiant inconnu : le site répond **200** avec un
   `<title>` vide et zéro ligne. Distinguer ce cas d'une épreuve vide légitime se
   fait sur le `<title>` : titre vide **et** zéro ligne → `ValueError` « épreuve
   introuvable ». Zéro ligne avec un titre valide reste une épreuve sans classé
   publié (liste vide, pas d'erreur). Sans cette garde explicite, le cas
   passerait en liste vide silencieuse : `_require_event_name` ne voit rien à
   refuser dans une liste vide.

4. **Métadonnées depuis le `<title>`** — seul porteur en français
   (`19/07/2026`), le bandeau rendant la date en anglais abrégé (`19 Jul 2026`).
   Le nom est nettoyé de son suffixe de distances entre parenthèses (FR-007a) ;
   le kilométrage total (`25.75KM`) alimente `distance_km` puisque
   `classify.extract_distance_km` ne trouve rien dans un nom sans « km ». La
   discipline passe par `classify.classify_event_type(nom)`, qui donne aussi la
   taille ; le `Type :` du titre ne sert que de repli quand le nom est muet.

5. **Colonnes lues par position, discipline par l'épreuve** — les 8 colonnes sont
   figées et leurs libellés mentent selon la discipline (cf. sondage). Le module
   vérifie le **nombre** de cellules (8) et ignore une ligne hors format en la
   journalisant, plutôt que de lire à l'aveugle. Les colonnes 2/3/5 vont dans
   `swim_time`/`bike_time`/`run_time` ; `mapping.build_splits` ré-étiquette
   (`duathlon` → `course1`/`bike`/`course2`, `aquathlon` → `swim`/`run`). Une
   cellule vide ne produit pas de segment.

6. **Pas de `segments`** — la liste ordonnée de `ScrapedResult.segments`
   (déplafonnée) n'est pas utilisée : le site publie au plus 3 segments et le
   chemin positionnel donne les bons libellés métier par discipline, ce que
   `segments` ne ferait qu'au prix de libellés en dur.

7. **Arrêt de pagination sur page sans ligne** (FR-004), avec un plafond de
   sécurité de pages (garde anti-boucle si le site se mettait à répéter la
   dernière page) journalisé s'il est atteint. Le total de classés (colonne 6)
   est capturé en `raw_data` mais **jamais** utilisé comme borne : il compte des
   équipes en relais (31 pour 62 lignes).

8. **Genre** — lu sur le suffixe de la catégorie (`S3M` → `M`, `MAF` → `F`),
   source disponible sur **toutes** les lignes. La classe du lien coureur
   (`<a class="M">`) n'existe que pour les inscrits au site : elle n'est pas
   utilisée, pour ne pas avoir deux sources partielles à réconcilier.

9. **Relais** — `is_relay` vrai si le nom d'épreuve ou la catégorie désigne une
   équipe (« duo », « relais », catégorie de la forme `X+Y`). Les deux signaux
   comptent : le nom qualifie l'épreuve entière, la catégorie confirme ligne par
   ligne. `chronoplace._is_relay_category` couvre déjà les libellés mais **pas**
   la forme `M+M` : on n'y touche pas (YAGNI, et le module chronoplace n'a pas à
   bouger pour ce provider) — la forme `X+Y` est testée localement.

10. **Lignes anonymes** — libellé `?DOSSARD #43637` détecté par son préfixe, rangé
    intégralement en `athlete_name`, `athlete_firstname` vide (FR-014), sans
    passer par `split_athlete_name` qui en ferait un prénom `#43637`.

11. **Statut** — le module ne se prononce pas (`status=""`) : aucun DNF/DNS/DSQ
    n'existe dans la source, `mapping.derive_status` applique son heuristique.

12. **`raw_data`** — accueille tout ce que le modèle n'a pas : rangs par segment,
    écarts en %, vitesses, rang avant la dernière course à pied et son évolution,
    évolution du rang final, total de classés annoncé, identifiant interne du
    coureur (`di`), page d'origine de la ligne.

13. **Avertissement de republication** — la mention « Chronométrée par X » est
    lue sur la première page ; si `X` correspond à un provider supporté, un
    `logger.warning` le signale une fois par épreuve. Aucune URL n'est
    reconstruite (le lien ne pointe que l'accueil du chronométreur), à l'identique
    du choix fait pour T2Area.

### Ce qui n'est **pas** fait, volontairement

- Aucune modification de `import_service` : la déduplication sans dossard existe
  déjà et est générique.
- Aucune inférence de club (arbitré).
- Aucun fan-out d'une fiche coureur (arbitré).
- Aucun assouplissement de `quality._rank_anomalies` pour les rangs partagés en
  relais : limite documentée, hors périmètre.
- Aucune factorisation du parsing HTML avec les autres providers.

## Phase 0 — Research

Le sondage du 27/07/2026 tient le rôle de la recherche exploratoire : il n'y a
aucun `NEEDS CLARIFICATION` résiduel dans le Technical Context. `research.md`
consigne les décisions techniques et les alternatives écartées, chacune adossée à
une mesure du sondage.

**Output**: [research.md](./research.md)

## Phase 1 — Design & Contracts

**Output**:

- [data-model.md](./data-model.md) — correspondance colonne du site → champ du
  modèle, et ce qui tombe en `raw_data`. Aucune entité, aucun champ, aucune
  migration.
- [contracts/provider-contract.md](./contracts/provider-contract.md) — le contrat
  `ScraperProtocol` et les invariants que les tests verrouillent.
- [quickstart.md](./quickstart.md) — vérification de bout en bout, avec les URLs
  réelles et les nombres attendus.
