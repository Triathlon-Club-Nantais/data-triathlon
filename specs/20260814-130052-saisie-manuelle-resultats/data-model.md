# Phase 1 — Modèle de données : saisie manuelle des résultats (#270)

**Feature** : `20260814-130052-saisie-manuelle-resultats` · **Date** : 2026-08-14

Une migration Alembic, quatre colonnes, aucun backfill. Les décisions sont
justifiées dans [research.md](./research.md) — ici, la forme exacte.

---

## 1. `participations` — trois colonnes

```python
# app/models/participation.py

# Résultat déclaré par un membre, pas encore vérifié par un bénévole (#270).
# Dimension **distincte** de `status` : un DNF déclaré reste un DNF une fois
# validé. Défaut `false` — les lignes existantes n'ont jamais été soumises à
# validation, les marquer pendantes serait faux.
is_pending_validation: Mapped[bool] = mapped_column(
    Boolean, default=False, server_default="false"
)

# Nom de l'équipe pour un résultat collectif. Sur la participation et non sur
# la course : deux équipes courent la même épreuve.
team_name: Mapped[str | None] = mapped_column(String, nullable=True)

# Lien vers les résultats publiés, saisi par le déclarant comme pièce
# justificative. **Jamais** une `CourseSource` : cf. research.md D5.
evidence_url: Mapped[str | None] = mapped_column(String, nullable=True)
```

**Contraintes** : aucune nouvelle. `uq_participation_bib`
(`UNIQUE(course_id, bib_number)`) est inchangée — deux saisies manuelles sans
dossard ne se heurtent donc pas, ce que le cas limite « doublon de la même
personne » de la spec prévoit explicitement (le doublon est *détectable* par le
bénévole, pas rejeté par la base).

**Index** : aucun. Cf. research.md, synthèse des changements de schéma.

### Règles de validation portées par le modèle

| Colonne | Règle | Où elle s'applique |
| --- | --- | --- |
| `is_pending_validation` | `True` sur tout résultat créé par `POST /participations`, `False` sur tout résultat créé par l'import | service, pas modèle — cf. §4 |
| `team_name` | Non vide si et seulement si `is_relay` est vrai | formulaire (FR-013) ; le backend ne le contraint pas |
| `evidence_url` | Aucune validation de forme côté modèle | cf. §5 |

---

## 2. `courses` — une colonne

```python
# app/models/course.py

# Précision libre du format quand il n'entre dans aucune taille normalisée
# (« Autre » du formulaire manuel, #270). Le format normalisé, lui, reste
# encodé dans `event_type` (`triathlon-m`) — cf. research.md D4.
format_label: Mapped[str | None] = mapped_column(String, nullable=True)
```

**N'entre pas dans `uq_course_identity`**, qui reste
`(name, event_date, event_type, is_relay)`. Deux épreuves qui ne diffèrent que
par leur précision de format sont la **même** épreuve : la précision décrit, elle
n'identifie pas.

---

## 3. Vocabulaire des états

### Statut sportif — `Participation.status`, inchangé

Valeurs de `app/scrapers/base.py` : `finisher`, `DNF`, `DNS` (et `DSQ`, produit
par certains scrapers, jamais saisissable à la main). **Aucune valeur nouvelle**
n'est introduite par cette feature.

### État de validation — `Participation.is_pending_validation`, nouveau

| Valeur | Signification | Qui la pose |
| --- | --- | --- |
| `False` | Résultat de confiance : importé d'un chronométreur, ou déclaré puis vérifié | l'import ; #271 à la validation |
| `True` | Déclaration non vérifiée | `POST /participations` |

**Les deux dimensions sont libres** : les huit combinaisons (4 statuts × 2 états)
sont représentables, et trois d'entre elles sont attendues dès cette feature —
`finisher` + pendant, `DNF` + pendant, `DNS` + pendant.

### Transition

```
[créé par saisie manuelle] ──> is_pending_validation = True
                                        │
                                        │  action humaine (#271)
                                        ▼
                               is_pending_validation = False
```

Une seule transition, un seul sens, déclenchée par un geste humain. Pas
d'expiration, pas de validation automatique (FR-018). **Le geste appartient à
#271** : cette feature écrit l'état initial et le lit, elle ne fournit pas la
bascule.

---

## 4. Écriture — qui pose `is_pending_validation`

Le point d'entrée manuel et le point d'entrée d'import partagent
`scrape_service.save_one` (`services/scrape_service.py:20`), appelé unitairement
par `POST /participations` et **en boucle** par l'import d'épreuve. La distinction
ne peut donc pas vivre dans `save_one`.

**Décision** : elle vit dans `mapping.participation_fields`, alimentée par un
champ porté par `ScrapedResult`, à défaut `False`.

```
POST /participations ──> ParticipationCreate.is_pending_validation = True (forcé)
                              │
                              ▼
                     _to_scraped() ──> ScrapedResult
                              │
                              ▼
                  mapping.participation_fields() ──> Participation

import d'épreuve ────> ScrapedResult (défaut False) ──> même chemin
```

**Le champ n'est pas laissé au client.** `ParticipationCreate` ne l'expose pas :
la route le force. Un champ d'entrée `is_pending_validation: false` permettrait à
tout porteur de `participations:write` de publier un résultat directement comme
vérifié, ce qui viderait FR-016 de son sens.

---

## 5. Le lien de vérification : ce qu'on ne valide pas

`evidence_url` est stocké **verbatim**, sans validation de forme au modèle ni au
schéma Pydantic. Le cas limite de la spec le demande explicitement : un texte qui
n'est pas une adresse exploitable *« ne doit ni bloquer l'enregistrement sur ce
seul motif, ni être présenté comme un lien cliquable »*.

La conséquence est donc **à l'affichage, pas au stockage** : le rendu ne
fabrique un `<a>` que pour une valeur reconnue comme URL `http`/`https`, et rend
le reste en texte brut. C'est aussi la garde qui évite un `javascript:` cliquable
posé par un contributeur — la valeur vient d'un formulaire authentifié mais reste
une donnée d'entrée.

---

## 6. Taxonomie des disciplines — les slugs à créer

Aucune table : `event_type` est une **chaîne sans clé étrangère**, dont la liste
de référence vit dans `scrapers/classify.CANONICAL_TYPES` (même patron que
`permission_code`, cf. `models/AGENTS.md`).

| Slug | Libellé UI | Statut |
| --- | --- | --- |
| `duathlon-xl` | Duathlon XL | à créer — comble un trou de la série existante |
| `aquathlon-xs` … `aquathlon-xl` | Aquathlon XS … XL | à créer — 5 slugs |
| `swim-bike` | Swim Bike | à créer, **base multi-mots** |
| `swim-bike-xs` … `swim-bike-xl` | Swim Bike XS … XL | à créer — 5 slugs |
| `cross-triathlon` | Cross Triathlon | à créer, **base multi-mots** |
| `raid-multisport` | Raid Multisport | à créer, **base multi-mots** |

**13 slugs**, dont 3 nouvelles bases de sport. Les quatre déclarations à tenir
d'équerre sont listées en research.md D3 ; le piège `_sport_base` — et
l'homonymie entre celui de `mapping.py` et celui de `classify.py` — y est
détaillé.

### Gabarits de splits des nouvelles bases

| Base | Gabarit `_SPLIT_KEYS_BY_SPORT` | Pourquoi |
| --- | --- | --- |
| `swim-bike` | `{swim_time: "swim", t1_time: "t1", bike_time: "bike"}` | pas de course à pied — le gabarit par défaut lui en inventerait une |
| `cross-triathlon` | **aucune entrée** | le gabarit par défaut (natation / T1 / vélo / T2 / course) est déjà juste |
| `raid-multisport` | `{}` ou positionnel | aucun découpage prévisible ; à trancher à l'implémentation, sans conséquence sur la saisie manuelle où les temps sont facultatifs |

---

## 7. Entités inchangées

- **`Athlete`** — aucune colonne, aucune règle nouvelle. Le rattachement passe par
  `athlete_repository.resolve`, inchangé. Un nom non reconnu **crée** un athlète,
  comportement actuel que la spec conserve (cas limite « nom d'athlète non
  reconnu »).
- **`CourseSource`** — **explicitement non touchée**, cf. research.md D5. Une
  épreuve déclarée n'a aucune source.
- **`Course.distance_km`** — existante, réutilisée telle quelle par le champ
  « distance totale » des disciplines sans format.
- **`Participation.rank_overall`** — existante, exposée par le champ « place
  générale ». Aucune migration.
- **`Participation.is_relay`** — existante, réutilisée par le choix
  individuel / collectif. Conséquence sur l'identité de la `Course` :
  research.md D6.
