# Implementation Plan: Support de chronoweb.com comme fournisseur de résultats

**Branch**: `feat-scrapers-supporter-chronoweb.com-html-stati` | **Date**: 2026-07-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-chronoweb-scraper/spec.md`

## Summary

Ajouter un fournisseur `chronoweb` au registre de scrapers : un module HTML
statique qui, en **une requête**, lit toutes les épreuves d'un événement
chronoweb.com et rend une `ScrapedResult` par participant et par épreuve. Une
seconde requête, facultative et non bloquante, va chercher la commune dans le
catalogue du site.

La difficulté n'est pas le markup (régulier sur les 89 épreuves du panel) mais
sa **sémantique** : une ligne du tableau est le passage d'un concurrent à un
point de chronométrage, pas un participant. Le scraper regroupe donc les lignes
par `(épreuve, dossard)`, prend temps total et rangs au dernier point franchi,
et convertit les durées de segment — plus deux transitions calculées — en
splits. Aucun changement de schéma, aucune migration, aucune modification de
contrat public.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: `httpx`, `BeautifulSoup` + `lxml` (déjà présents ;
aucune dépendance nouvelle — cf. research R1)

**Storage**: aucune évolution — `Athlete` / `Course` / `Participation`
existants, alimentés par `services/mapping`

**Testing**: pytest ; unitaires sans réseau (monkeypatch `httpx.Client`,
fixtures HTML réduites), réseau réel derrière le marker `integration`

**Target Platform**: backend FastAPI (Render), CLI d'import de masse

**Project Type**: web application (backend + frontend), feature backend-only à
une exception près (libellé commercial du fournisseur côté front)

**Performance Goals**: import d'un événement de 1 622 participants en une
requête ; mesuré sur la page la plus lourde du panel (4,5 Mo) : 1,09 s de
téléchargement, 1,20 s de parse, 0,75 s d'extraction, 144 Mo de RSS au pic

**Constraints**: au plus 2 requêtes HTTP au site par import ; aucune dépendance
à la page de détail d'un participant (cassée à la source sur les épreuves
mono-point) ; aucun balayage du catalogue

**Scale/Scope**: 222 événements publiés par le site, 7 liens dans le Sheet ; le
panel de sondage couvre 21 événements / 89 épreuves / 14 015 participants

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.0.0).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Module, identifiants, docstrings et tests en anglais ; messages d'erreur destinés à l'opérateur (`ValueError` remontée en `ProviderNotSupportedError`, puis affichée) en français, comme la règle du cas mixte `DomainError`. Décision tracée dans § Clarifications de la spec. |
| II | Architecture en couches | ✅ | Le scraper vit dans `app/scrapers/`, ne touche ni `Session` ni repository, et rend des `ScrapedResult`. Aucune règle club n'est réimplémentée — la source ne publie pas de club. |
| III | TDD sans réseau | ✅ | Tests unitaires sur fixtures HTML verbatim réduites, `httpx.Client` monkeypatché ; réseau réel isolé derrière `integration` (research R9). Chaque tâche d'implémentation part d'un test rouge. |
| IV | Contrats API et CLI stables | ✅ | Aucun contrat modifié. Seul effet : `GET /scrape/detect` répond désormais `supported: true` sur ce host, et `chronoweb` devient une valeur acceptée de `--provider` — deux élargissements, pas des ruptures. |
| V | Neutralité des paramètres transverses | N/A | La feature n'introduit ni ne modifie aucun paramètre transverse de l'API de lecture. |
| VI | Simplicité / YAGNI | ✅ | Un seul module, pas d'abstraction partagée nouvelle ; réutilisation de `normalize_time`, `split_athlete_name`, `qualify_event_name`, `classify_event_type`, `build_splits`, `derive_status`. Dépendance `cssselect` écartée bien que 24× plus rapide au parse : le gain est sans objet (research R1). |

**Re-check post-Phase 1** : inchangé. Les artefacts de conception n'introduisent
ni couche, ni dépendance, ni contrat supplémentaire.

## Project Structure

### Documentation (this feature)

```text
specs/005-chronoweb-scraper/
├── plan.md              # Ce fichier
├── spec.md              # Spécification (avec § Clarifications)
├── research.md          # Phase 0 — 9 décisions mesurées
├── data-model.md        # Phase 1 — structures internes + correspondance de sortie
├── quickstart.md        # Phase 1 — commandes de vérification
├── contracts/
│   └── provider.md      # Phase 1 — contrat de registre et de sortie
├── checklists/
│   └── requirements.md  # Qualité de la spec
└── tasks.md             # Phase 2 (/speckit-tasks — non créé ici)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── scrapers/
│       ├── chronoweb.py          # NOUVEAU — le fournisseur
│       └── registry.py           # MODIFIÉ — ChronoWebProvider ajouté à PROVIDERS
└── tests/
    ├── test_chronoweb.py         # NOUVEAU — unitaires + integration
    └── fixtures/
        └── chronoweb/            # NOUVEAU — 7 fixtures HTML réduites verbatim

frontend/
└── lib/constants.ts              # MODIFIÉ — PROVIDER_LABELS: chronoweb → « ChronoWeb »

docs/superpowers/specs/
└── 2026-07-29-chronoweb-sondage.md   # DÉJÀ ÉCRIT — vérité de terrain

AGENTS.md                         # MODIFIÉ — section « Fournisseurs supportés »
```

**Structure Decision**: aucune structure nouvelle. Le fournisseur suit à la
lettre le patron des deux derniers ajoutés (`runnerbreizh.py`, `t2area.py`) :
un module par fournisseur, un adapter déclaratif dans `registry.py`, un fichier
de tests, un dossier de fixtures. La seule touche frontend est une entrée de
libellé commercial — le front ne liste jamais les fournisseurs supportés, il lit
`is_supported` depuis l'API.

## Découpage d'implémentation (pré-tasks)

Ordre pensé pour que chaque étape soit testable seule, du plus structurant au
plus périphérique. `/speckit-tasks` le détaillera.

1. **Fixtures** — extraire les 7 fixtures réduites depuis les pages du panel
   (script d'extraction jetable, sorties versionnées). Prérequis de tout le
   reste (principe III).
2. **URL** — canonicalisation par allowlist, troncature de la fiche
   individuelle, refus motivé des autres formes (research R5).
3. **Lecture de la page** — métadonnées d'événement, sélecteur d'épreuves,
   lignes de passage ; gardes « événement inconnu » vs « sans classement ».
4. **Regroupement** — passages → participants ; temps total et rangs au dernier
   point.
5. **Segments** — table de motifs, transitions calculées, repli sur segments
   étiquetés (research R2, R3).
6. **Identité** — genre par catégorie, relais et noms d'équipe (research R6, R7).
7. **Commune** — requête d'appoint sur le catalogue, échec non bloquant (R4).
8. **Registre** — `ChronoWebProvider`, tests de détection et de non-régression
   sur les autres fournisseurs.
9. **Périphérie** — libellé front, section `AGENTS.md`, test `integration`.

## Risques identifiés

| Risque | Parade |
| --- | --- |
| Le site change de markup | Le sondage est daté et versionné ; les fixtures sont verbatim, donc un test qui casse pointe le changement réel. |
| Un motif de points hors des 5 connus | Repli sur segments étiquetés — aucune perte de données, aucun crash (research R2). |
| Page de 4,5 Mo en mémoire sur Render | Mesuré à 144 Mo de RSS au pic, une seule page à la fois. |
| Classifieur d'épreuves imprécis sur 3 épreuves du panel | Hors périmètre pour le **remplissage** des slots, qui suit le motif observé et non le type classé. Mais l'**étiquetage** aval, lui, dépend du type : `mapping.build_splits` filtre les slots par gabarit de sport (`mapping.py:83-88`), donc un motif `N→V→C` sur une épreuve mal classée `aquathlon` perdrait `bike` et `t2` — le mode d'échec que le dépôt a déjà payé une fois (un slot omis du gabarit jette sans bruit le temps qui s'y trouve). Vérifié sain sur les 89 épreuves du panel (research R2, § Vérifié) : chaque couple (motif, type classé) produit un jeu de clés cohérent, cas dégradés compris. Le risque résiduel se réalise donc au premier motif inédit **combiné** à un classement faux — il se traiterait dans le ticket dédié au classifieur, pas ici. |

## Complexity Tracking

> Aucune violation de la constitution à justifier : les 6 principes sont ✅ ou
> N/A. Section laissée vide intentionnellement.
