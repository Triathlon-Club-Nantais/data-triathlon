# Bande personnelle « Ma saison » — plan d'implémentation (NAV-9, #502)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insérer au-dessus des compteurs club de `/dashboard` une bande « Ma saison » qui met les épreuves et les podiums de l'athlète retenu en regard de ceux du club, sur exactement la même sélection de saisons, de disciplines et de type de rang.

**Architecture:** L'athlète retenu vit en `localStorage` et ne franchit pas la frontière serveur (arbitrage #467). La bande est donc un composant **client** monté sous un `/dashboard` qui reste rendu serveur : il lit le stock par un nouveau hook `useSelectedAthlete()`, appelle `GET /athletes/{id}` — qui gagne ici deux filtres optionnels `seasons` et `federal_only` — et compte deux entiers dans une fonction pure qui reprend littéralement le calcul de rang de `stats_service._rank_counters`. Les chiffres du club, eux, sont passés en props depuis le rendu serveur.

**Tech Stack:** Backend Python 3.13 / FastAPI / SQLAlchemy 2.0 sync, tests pytest (`uv run pytest -m "not integration"`). Frontend Next.js 16 App Router / TypeScript / Tailwind, tests vitest + `@testing-library/react` (`npm test`).

**Spec:** `docs/superpowers/specs/2026-08-25-ma-saison-bande-personnelle-design.md`

## Global Constraints

- **Langue** (Principe I de la constitution) : **français** pour tout ce qui est visible utilisateur ou métier — libellés d'UI, commentaires de règle métier, noms de tests français côté backend (`test_fiche_athlete_...`) et descriptions de `describe`/`it` côté frontend. **English** pour la couche technique invisible et les préfixes Conventional Commits.
- **TDD non négociable** (Principe III) : le test s'écrit et échoue **avant** l'implémentation, à chaque tâche.
- **Pas de compatibilité ascendante à préserver** dans le code interne — *une exception, contractuelle* : l'API `/api/v1` publiée. Les deux paramètres ajoutés ici sont **optionnels et neutres par défaut** (`seasons=None`, `federal_only=False`), ce qui est le seul motif qui les rend acceptables au titre du Principe IV.
- **Pas de cookie miroir de l'athlète retenu** (`frontend/AGENTS.md:218-245`) : aucune tâche de ce plan ne fait franchir la frontière serveur au stock `tcn-athlete`.
- **Identité visuelle non rejugée** : tokens `--tcn-*`, Anton/Barlow ; frontière `components/tcn/` (identité TCN) vs `components/ui/` (shadcn) inchangée.
- **Vouvoiement** dans toute microcopie utilisateur, conformément à #478.
- **Le RTK est autorisé** sur les commandes de test : `rtk uv run pytest …`, `rtk npm test`.

## Préalable — dépendances du worktree

Le worktree n'hérite d'aucun fichier gitignoré. Avant la première tâche :

```bash
cd backend && uv sync
cd ../frontend && npm install
```

Vérifier que les deux suites partent au vert **avant** toute modification :

```bash
cd backend && uv run pytest -m "not integration" -q
cd ../frontend && npm test
```

---

### Task 1: Filtres saison et discipline sur `list_for_athlete`

**Files:**
- Modify: `backend/app/repositories/participation_repository.py:376-383`
- Test: `backend/tests/test_repositories/test_participation_repository.py`

**Interfaces:**
- Consumes: `season_clause(seasons)` (`participation_repository.py:276`), `federal_clause(column)` (`app/core/discipline.py:40`) — les deux déjà importés en tête du fichier.
- Produces: `list_for_athlete(db, athlete_id, *, seasons: list[int] | None = None, federal_only: bool = False) -> list[Participation]`.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `backend/tests/test_repositories/test_participation_repository.py` :

```python
# ── list_for_athlete : filtres saison / discipline (#502) ────────────────────


def _course_pour_filtre(db_session, nom, event_date, event_type):
    from app.repositories import course_repository

    course = course_repository.get_or_create(
        db_session,
        name=nom,
        event_date=event_date,
        event_type=event_type,
        source_url=f"https://k/{nom}",
        provider="klikego",
    )
    db_session.flush()
    return course


def _athlete_avec_trois_courses(db_session):
    """Un athlète, trois participations : saison 2025 triathlon, saison 2025
    trail, saison 2024 triathlon. Chaque filtre en retire une différente."""
    from datetime import date

    from app.repositories import athlete_repository, participation_repository

    athlete = athlete_repository.get_or_create(db_session, nom="FILTRE", prenom="Fanny")
    db_session.flush()
    courses = {
        "tri_2025": _course_pour_filtre(db_session, "Tri 2025", date(2025, 10, 5), "triathlon-m"),
        "trail_2025": _course_pour_filtre(db_session, "Trail 2025", date(2025, 10, 12), "trail"),
        "tri_2024": _course_pour_filtre(db_session, "Tri 2024", date(2024, 10, 5), "triathlon-m"),
    }
    for i, course in enumerate(courses.values(), start=1):
        participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=str(i),
            club="Triathlon Club Nantais",
        )
    db_session.commit()
    return athlete


def test_list_for_athlete_sans_filtre_rend_tout(db_session):
    from app.repositories import participation_repository

    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(db_session, athlete.id)

    assert len(lignes) == 3


def test_list_for_athlete_filtre_par_saison(db_session):
    from app.repositories import participation_repository

    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(db_session, athlete.id, seasons=[2025])

    assert sorted(p.course.name for p in lignes) == ["Trail 2025", "Tri 2025"]


def test_list_for_athlete_federal_only_retire_le_trail(db_session):
    from app.repositories import participation_repository

    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(db_session, athlete.id, federal_only=True)

    assert sorted(p.course.name for p in lignes) == ["Tri 2024", "Tri 2025"]


def test_list_for_athlete_combine_saison_et_discipline(db_session):
    from app.repositories import participation_repository

    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(
        db_session, athlete.id, seasons=[2025], federal_only=True
    )

    assert [p.course.name for p in lignes] == ["Tri 2025"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_repositories/test_participation_repository.py -k list_for_athlete -v`
Expected: FAIL — `TypeError: list_for_athlete() got an unexpected keyword argument 'seasons'` sur trois des quatre tests (le premier, sans filtre, passe déjà).

- [ ] **Step 3: Write minimal implementation**

Remplacer `backend/app/repositories/participation_repository.py:376-383` par :

```python
def list_for_athlete(
    db: Session,
    athlete_id: int,
    *,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[Participation]:
    """Participations d'un athlète, filtrables comme les agrégats du club (#502).

    Les deux filtres sont **neutres par défaut** : la fiche athlète
    (`GET /athletes/{id}` sans paramètre) continue de rendre une carrière
    entière. Ils n'existent que pour la bande « Ma saison » du tableau de bord,
    qui doit compter sur exactement la même base que les compteurs club — d'où
    les mêmes clauses que `for_stats`, et non une recopie.
    """
    q = (
        db.query(Participation)
        .options(joinedload(Participation.course).selectinload(Course.sources))
        .filter(Participation.athlete_id == athlete_id)
    )
    if seasons or federal_only:
        q = q.join(Course, Participation.course_id == Course.id)
    if seasons:
        q = q.filter(season_clause(seasons))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.order_by(Participation.created_at.desc()).all()
```

Note pour l'implémenteur : `joinedload(Participation.course)` cohabite avec un `.join(Course, …)` explicite — c'est exactement ce que fait déjà `for_stats` (`:589-599`), aucune surprise SQLAlchemy à attendre.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_repositories/test_participation_repository.py -k list_for_athlete -v`
Expected: PASS (4 tests)

Puis la non-régression du fichier entier : `uv run pytest tests/test_repositories/test_participation_repository.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/participation_repository.py backend/tests/test_repositories/test_participation_repository.py
git commit -m "feat(502): filtres saison et discipline sur list_for_athlete"
```

---

### Task 2: Les deux paramètres sur `GET /athletes/{id}`

**Files:**
- Modify: `backend/app/api/v1/athletes.py:78-93`
- Test: `backend/tests/test_api/test_athletes_api.py`

**Interfaces:**
- Consumes: `list_for_athlete(db, athlete_id, *, seasons, federal_only)` (Task 1) ; `parse_seasons(raw: str | None) -> list[int]` (`app/core/season.py:31`, déjà importé dans `athletes.py`).
- Produces: la route `GET /api/v1/athletes/{athlete_id}?seasons=<CSV>&federal_only=<bool>`, réponse inchangée dans sa forme (`{"athlete": …, "participations": [...]}`).

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `backend/tests/test_api/test_athletes_api.py` :

```python
# ── GET /athletes/{id} : filtres saison / discipline (#502) ──────────────────


def _athlete_trois_saisons(client, db_session):
    """Le même corpus que le test de repository, vu depuis la route."""
    from app.repositories import athlete_repository, course_repository, participation_repository

    athlete = athlete_repository.get_or_create(db_session, nom="BANDE", prenom="Bruno")
    db_session.flush()
    corpus = [
        ("Tri 2025", date(2025, 10, 5), "triathlon-m"),
        ("Trail 2025", date(2025, 10, 12), "trail"),
        ("Tri 2024", date(2024, 10, 5), "triathlon-m"),
    ]
    for i, (nom, jour, type_epreuve) in enumerate(corpus, start=1):
        course = course_repository.get_or_create(
            db_session, name=nom, event_date=jour, event_type=type_epreuve,
            source_url=f"https://k/{nom}", provider="klikego",
        )
        db_session.flush()
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id,
            bib_number=str(i), club="Triathlon Club Nantais",
        )
    db_session.commit()
    return athlete


def test_fiche_athlete_sans_parametre_rend_la_carriere_entiere(client, db_session):
    """Non-régression du contrat publié : les deux filtres de #502 sont neutres
    par défaut, la fiche athlète ne change pas de comportement."""
    athlete = _athlete_trois_saisons(client, db_session)

    detail = client.get(f"/api/v1/athletes/{athlete.id}").json()

    assert len(detail["participations"]) == 3


def test_fiche_athlete_filtre_par_saison(client, db_session):
    athlete = _athlete_trois_saisons(client, db_session)

    detail = client.get(
        f"/api/v1/athletes/{athlete.id}", params={"seasons": "2025"}
    ).json()

    assert sorted(p["course"]["name"] for p in detail["participations"]) == [
        "Trail 2025",
        "Tri 2025",
    ]


def test_fiche_athlete_federal_only_retire_les_disciplines_hors_federation(client, db_session):
    athlete = _athlete_trois_saisons(client, db_session)

    detail = client.get(
        f"/api/v1/athletes/{athlete.id}", params={"federal_only": "true"}
    ).json()

    assert sorted(p["course"]["name"] for p in detail["participations"]) == [
        "Tri 2024",
        "Tri 2025",
    ]


def test_fiche_athlete_combine_les_deux_filtres(client, db_session):
    athlete = _athlete_trois_saisons(client, db_session)

    detail = client.get(
        f"/api/v1/athletes/{athlete.id}",
        params={"seasons": "2025", "federal_only": "true"},
    ).json()

    assert [p["course"]["name"] for p in detail["participations"]] == ["Tri 2025"]


def test_fiche_athlete_saisons_non_parsables_valent_toutes_saisons(client, db_session):
    """`parse_seasons` ignore les valeurs non entières et rend une liste vide,
    qui vaut « pas de filtre » — pas de 422, pas de 500."""
    athlete = _athlete_trois_saisons(client, db_session)

    detail = client.get(
        f"/api/v1/athletes/{athlete.id}", params={"seasons": "abc"}
    ).json()

    assert len(detail["participations"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_api/test_athletes_api.py -k "fiche_athlete_filtre or fiche_athlete_federal or fiche_athlete_combine or fiche_athlete_saisons" -v`
Expected: FAIL — les paramètres sont ignorés par la route, les trois filtres rendent encore 3 participations.

- [ ] **Step 3: Write minimal implementation**

Remplacer `backend/app/api/v1/athletes.py:78-93` par :

```python
@router.get("/athletes/{athlete_id}")
def get_athlete(
    athlete_id: int,
    seasons: str | None = Query(None),
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Fiche athlète et ses participations.

    Les deux filtres sont **optionnels et neutres par défaut** (#502) : sans
    eux, la route rend la carrière entière, comme depuis toujours. Ils servent
    la bande « Ma saison » du tableau de bord, qui doit compter sur la même
    base que les compteurs club affichés juste dessous — mêmes noms et mêmes
    sémantiques que sur `/stats` et `/athletes/season-activity`.
    """
    athlete = athlete_repository.get(db, athlete_id)
    if not athlete:
        raise NotFoundError("Athlète introuvable")
    participations = participation_repository.list_for_athlete(
        db, athlete_id, seasons=parse_seasons(seasons), federal_only=federal_only
    )
    counts = participation_repository.finishers_count_by_group(
        db, [p.course_id for p in participations]
    )
    items = []
    for p in participations:
        item = AthleteParticipationOut.model_validate(p)
        item.course_finishers = counts.get((p.course_id, bool(p.is_relay)))
        items.append(item)
    return {"athlete": AthleteBrief.model_validate(athlete), "participations": items}
```

`Query` et `parse_seasons` sont déjà importés en tête de `athletes.py` (lignes 2 et 8) — rien à ajouter aux imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_api/test_athletes_api.py -v`
Expected: PASS — les 5 nouveaux tests et les anciens.

Puis la suite entière : `cd backend && uv run pytest -m "not integration" -q` → PASS. Et `uv run ruff check .` → clean.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/athletes.py backend/tests/test_api/test_athletes_api.py
git commit -m "feat(502): optional seasons and federal_only filters on GET /athletes/{id}"
```

---

### Task 3: Le comptage, en fonctions pures

**Files:**
- Create: `frontend/lib/utils/ma-saison.ts`
- Create: `frontend/lib/utils/ma-saison.test.ts`
- Modify: `frontend/lib/utils/format.ts` (ajout de `motCompte`)
- Modify: `frontend/components/dashboard/StatCardsRank.tsx:47-50` (retire sa copie locale de `motCompte`)
- Test: `frontend/lib/utils/format.test.ts`

**Interfaces:**
- Consumes: `Participation` (`lib/types.ts:94`), `RankType` (`lib/rank.ts`).
- Produces:
  - `rangPourMode(p: Participation, mode: RankType): number | null`
  - `compteMaSaison(participations: Participation[], mode: RankType): { epreuves: number; podiums: number }`
  - `motCompte(n: number, mot: string): string` exporté depuis `lib/utils/format.ts`

- [ ] **Step 1: Write the failing test**

Créer `frontend/lib/utils/ma-saison.test.ts` :

```ts
import { describe, it, expect } from "vitest";
import type { Participation } from "@/lib/types";
import { compteMaSaison, rangPourMode } from "./ma-saison";

/** Participation minimale : seuls les champs que le comptage lit sont posés. */
function participation(over: {
  courseId: number;
  rank_overall?: number | null;
  rank_category?: number | null;
  rank_gender?: number | null;
  is_pending_validation?: boolean;
}): Participation {
  return {
    course: { id: over.courseId },
    rank_overall: over.rank_overall ?? null,
    rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null,
    is_pending_validation: over.is_pending_validation ?? false,
  } as unknown as Participation;
}

describe("rangPourMode — miroir de stats_service._rank_counters", () => {
  const p = participation({
    courseId: 1,
    rank_overall: 12,
    rank_category: 3,
    rank_gender: 7,
  });

  it("scratch lit rank_overall", () => {
    expect(rangPourMode(p, "scratch")).toBe(12);
  });

  it("category lit rank_category", () => {
    expect(rangPourMode(p, "category")).toBe(3);
  });

  it("gender lit rank_gender", () => {
    expect(rangPourMode(p, "gender")).toBe(7);
  });

  it("all prend le meilleur des trois", () => {
    expect(rangPourMode(p, "all")).toBe(3);
  });

  it("all ignore les rangs absents", () => {
    const partiel = participation({ courseId: 1, rank_overall: null, rank_gender: 5 });
    expect(rangPourMode(partiel, "all")).toBe(5);
  });

  it("all rend null quand aucun rang n'est connu", () => {
    expect(rangPourMode(participation({ courseId: 1 }), "all")).toBeNull();
  });

  // `_accumule` sort tout de suite sur `rang < 1` : un 0 est une donnée
  // aberrante du chronométreur, pas une victoire.
  it("écarte un rang inférieur à 1", () => {
    expect(rangPourMode(participation({ courseId: 1, rank_overall: 0 }), "scratch")).toBe(0);
    expect(compteMaSaison([participation({ courseId: 1, rank_overall: 0 })], "scratch").podiums).toBe(0);
  });
});

describe("compteMaSaison", () => {
  it("compte les courses distinctes, pas les dossards", () => {
    // Solo + relais sur la même course : une seule épreuve courue.
    const lignes = [
      participation({ courseId: 7, rank_overall: 40 }),
      participation({ courseId: 7, rank_overall: 2 }),
      participation({ courseId: 9, rank_overall: 15 }),
    ];
    expect(compteMaSaison(lignes, "scratch").epreuves).toBe(2);
  });

  it("compte un podium à partir du rang 3 inclus", () => {
    const lignes = [
      participation({ courseId: 1, rank_overall: 1 }),
      participation({ courseId: 2, rank_overall: 3 }),
      participation({ courseId: 3, rank_overall: 4 }),
      participation({ courseId: 4, rank_overall: null }),
    ];
    expect(compteMaSaison(lignes, "scratch").podiums).toBe(2);
  });

  it("change de compte selon le mode de rang", () => {
    const lignes = [
      participation({ courseId: 1, rank_overall: 40, rank_category: 2, rank_gender: 25 }),
    ];
    expect(compteMaSaison(lignes, "scratch").podiums).toBe(0);
    expect(compteMaSaison(lignes, "category").podiums).toBe(1);
    expect(compteMaSaison(lignes, "gender").podiums).toBe(0);
    expect(compteMaSaison(lignes, "all").podiums).toBe(1);
  });

  it("exclut les résultats en attente de validation", () => {
    const lignes = [
      participation({ courseId: 1, rank_overall: 1 }),
      participation({ courseId: 2, rank_overall: 1, is_pending_validation: true }),
    ];
    expect(compteMaSaison(lignes, "scratch")).toEqual({ epreuves: 1, podiums: 1 });
  });

  it("rend deux zéros sur une liste vide", () => {
    expect(compteMaSaison([], "scratch")).toEqual({ epreuves: 0, podiums: 0 });
  });
});
```

Ajouter à `frontend/lib/utils/format.test.ts` :

```ts
describe("motCompte", () => {
  it("laisse le singulier à 1", () => {
    expect(motCompte(1, "podium")).toBe("1 podium");
  });

  it("accorde au pluriel au-delà", () => {
    expect(motCompte(2, "podium")).toBe("2 podiums");
    expect(motCompte(4, "épreuve")).toBe("4 épreuves");
  });

  // Le zéro français est singulier — « 0 podium », pas « 0 podiums ».
  it("laisse le singulier à 0", () => {
    expect(motCompte(0, "épreuve")).toBe("0 épreuve");
  });
});
```

(et compléter l'`import { … } from "./format"` en tête du fichier avec `motCompte`)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run lib/utils/ma-saison.test.ts lib/utils/format.test.ts`
Expected: FAIL — `Failed to resolve import "./ma-saison"` et `motCompte is not a function`.

- [ ] **Step 3: Write minimal implementation**

Créer `frontend/lib/utils/ma-saison.ts` :

```ts
import type { RankType } from "@/lib/rank";
import type { Participation } from "@/lib/types";

/**
 * Rang à lire pour un mode du toggle du tableau de bord.
 *
 * **Miroir littéral de `stats_service._rank_counters`** (backend) : c'est ce
 * qui rend « mon » podium comparable à celui du club affiché juste dessous. Le
 * mode `all` prend le meilleur des trois rangs, comme `_meilleur_rang`. Toute
 * divergence ici rendrait la mise en regard fausse sans qu'elle se voie.
 */
export function rangPourMode(p: Participation, mode: RankType): number | null {
  if (mode === "scratch") return p.rank_overall;
  if (mode === "category") return p.rank_category;
  if (mode === "gender") return p.rank_gender;
  const connus = [p.rank_overall, p.rank_gender, p.rank_category].filter(
    (r): r is number => r != null && r >= 1,
  );
  return connus.length > 0 ? Math.min(...connus) : null;
}

/** Les deux chiffres de la bande « Ma saison » (#502). */
export type CompteursMaSaison = { epreuves: number; podiums: number };

/**
 * Épreuves courues et podiums d'un athlète sur les participations reçues.
 *
 * Deux règles reprises du club, sans quoi la comparaison serait bancale :
 * les résultats **en attente de validation** sont exclus (comme
 * `for_stats`, #270/FR-021), et les épreuves se comptent en **courses
 * distinctes** — un athlète inscrit en solo *et* en relais sur la même course
 * y compterait sinon pour deux, là où `stats.events` la compte une fois.
 */
export function compteMaSaison(
  participations: Participation[],
  mode: RankType,
): CompteursMaSaison {
  const validees = participations.filter((p) => !p.is_pending_validation);
  const podiums = validees.filter((p) => {
    const rang = rangPourMode(p, mode);
    return rang != null && rang >= 1 && rang <= 3;
  }).length;
  return { epreuves: new Set(validees.map((p) => p.course.id)).size, podiums };
}
```

Ajouter à `frontend/lib/utils/format.ts` :

```ts
/**
 * « 1 podium » / « 2 podiums » — décompte accordé, pour les zones dont le
 * contenu change sans navigation et doit rester lisible à l'annonce (#477).
 * Le zéro reste au singulier, comme le veut le français.
 */
export function motCompte(n: number, mot: string): string {
  return `${n} ${mot}${n > 1 ? "s" : ""}`;
}
```

Puis, dans `frontend/components/dashboard/StatCardsRank.tsx` : supprimer la définition locale de `motCompte` (lignes 47-50 avec son commentaire `/** Décompte annoncé (#477) … */`) et l'importer depuis `@/lib/utils/format`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run lib/utils/ma-saison.test.ts lib/utils/format.test.ts components/dashboard/StatCardsRank.test.tsx`
Expected: PASS — dont `StatCardsRank`, qui doit rester vert après le déplacement de `motCompte`.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/utils/ma-saison.ts frontend/lib/utils/ma-saison.test.ts frontend/lib/utils/format.ts frontend/lib/utils/format.test.ts frontend/components/dashboard/StatCardsRank.tsx
git commit -m "feat(502): compte des épreuves et podiums d'un athlète, par mode de rang"
```

---

### Task 4: Le hook `useSelectedAthlete`

**Files:**
- Modify: `frontend/components/layout/AthletePicker.tsx` (après `useIsSelectedAthlete`, ligne 100)
- Test: `frontend/components/layout/AthletePicker.test.tsx`

**Interfaces:**
- Consumes: `STORE` (`"tcn-athlete"`), `readAthlete()`, `subscribeAthlete()`, `PickedAthlete` — tous déjà dans le fichier.
- Produces: `useSelectedAthlete(): PickedAthlete | null`

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/components/layout/AthletePicker.test.tsx` :

```tsx
describe("useSelectedAthlete", () => {
  function Sonde() {
    const athlete = useSelectedAthlete();
    return <span data-testid="sonde">{athlete ? `${athlete.id}:${athlete.nom}` : "aucun"}</span>;
  }

  it("rend null quand aucun athlète n'est retenu", () => {
    render(<Sonde />);
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");
  });

  it("rend l'athlète retenu", () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    render(<Sonde />);
    expect(screen.getByTestId("sonde")).toHaveTextContent(`${ATHLETE.id}:${ATHLETE.nom}`);
  });

  it("suit un choix fait ailleurs dans la page", () => {
    render(<Sonde />);
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");

    act(() => writeAthlete(ATHLETE));
    expect(screen.getByTestId("sonde")).toHaveTextContent(`${ATHLETE.id}:${ATHLETE.nom}`);

    act(() => clearAthlete());
    expect(screen.getByTestId("sonde")).toHaveTextContent("aucun");
  });

  // `useSyncExternalStore` boucle si `getSnapshot` rend un objet neuf à chaque
  // appel — c'est la raison pour laquelle `useIsSelectedAthlete` rend un
  // booléen. Ce hook lève la contrainte par un cache, ce test le garde.
  it("rend la même référence tant que le stock ne change pas", () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    const vues: (unknown | null)[] = [];
    function Collecte() {
      vues.push(useSelectedAthlete());
      return null;
    }
    const { rerender } = render(<Collecte />);
    rerender(<Collecte />);

    expect(vues.length).toBeGreaterThanOrEqual(2);
    expect(vues[0]).toBe(vues[vues.length - 1]);
  });

  it("rend une nouvelle référence après un changement de stock", () => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
    const vues: (unknown | null)[] = [];
    function Collecte() {
      vues.push(useSelectedAthlete());
      return null;
    }
    render(<Collecte />);
    const avant = vues[vues.length - 1];

    act(() => writeAthlete(AUTRE));

    expect(vues[vues.length - 1]).not.toBe(avant);
    expect(vues[vues.length - 1]).toMatchObject({ id: AUTRE.id });
  });
});
```

Note pour l'implémenteur : le fichier de test définit déjà `ATHLETE` ; ajouter à côté `const AUTRE = { id: 99, prenom: "Marie", nom: "Gaudin" };` s'il n'y est pas, et compléter les imports (`act`, `render`, `screen` de `@testing-library/react` ; `useSelectedAthlete`, `clearAthlete` depuis `./AthletePicker`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx`
Expected: FAIL — `useSelectedAthlete is not a function`.

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `frontend/components/layout/AthletePicker.tsx`, juste après `useIsSelectedAthlete` :

```ts
/**
 * Cache d'instantané du stock. `useSyncExternalStore` exige que `getSnapshot`
 * rende une valeur **stable** d'un appel à l'autre sous peine de boucler, or
 * `readAthlete()` reconstruit un objet à chaque lecture. On mémoïse donc sur la
 * chaîne brute : tant qu'elle ne bouge pas, la même référence est rendue.
 *
 * Module-level à dessein : le stock est unique par document, les abonnés
 * partagent donc légitimement le même instantané.
 */
let brutEnCache: string | null = null;
let athleteEnCache: PickedAthlete | null = null;

function snapshotAthlete(): PickedAthlete | null {
  let brut: string | null = null;
  try {
    brut = window.localStorage.getItem(STORE);
  } catch {
    /* mode privé : traité comme une absence de choix, cohérent avec readAthlete. */
  }
  if (brut !== brutEnCache) {
    brutEnCache = brut;
    athleteEnCache = readAthlete();
  }
  return athleteEnCache;
}

/**
 * L'athlète retenu, ou `null`. Pendant du booléen `useIsSelectedAthlete`, pour
 * les écrans qui ont besoin de *qui* et pas seulement de *est-ce lui* — la
 * bande « Ma saison » du tableau de bord (#502).
 *
 * Comme son voisin : `null` au rendu serveur, la lecture réelle dès
 * l'hydratation. Le stock ne franchit pas la frontière serveur
 * (`frontend/AGENTS.md:218-245`).
 */
export function useSelectedAthlete(): PickedAthlete | null {
  return useSyncExternalStore(subscribeAthlete, snapshotAthlete, () => null);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AthletePicker.tsx frontend/components/layout/AthletePicker.test.tsx
git commit -m "feat(502): useSelectedAthlete, pendant de useIsSelectedAthlete"
```

---

### Task 5: `apiClient.getAthlete` et le composant `MaSaison`

**Files:**
- Modify: `frontend/lib/api/client.ts` (à côté de `searchAthletes`, ligne 159)
- Create: `frontend/components/dashboard/MaSaison.tsx`
- Create: `frontend/components/dashboard/MaSaison.test.tsx`

**Interfaces:**
- Consumes: `compteMaSaison` (Task 3), `motCompte` (Task 3), `useSelectedAthlete` (Task 4), `nomComplet` (`AthletePicker.tsx:30`), `rankTypeFromParam`/`RANK_PARAM` (`lib/rank.ts`), `rankTypeLabel` (`lib/labels.ts`), `AnnonceStatut`/`Card`/`Eyebrow` (`@/components/tcn`), `Skeleton` (`@/components/ui/skeleton`), `AthleteDetail` (`lib/types.ts:434`).
- Produces:
  - `apiClient.getAthlete(id: number, filters?: { seasons?: string; federal_only?: boolean }): Promise<AthleteDetail>`
  - `<MaSaison clubEvents={number} seasons={string} federalOnly={boolean | undefined} />`

**Note de conception** : `seasons` est une **chaîne CSV**, pas un tableau. C'est ce que `toQuery` envoie de toute façon, et une primitive est une dépendance de `useEffect` stable — un tableau recréé à chaque rendu relancerait le fetch en boucle.

- [ ] **Step 1: Write the failing test**

Créer `frontend/components/dashboard/MaSaison.test.tsx` :

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import type { Participation } from "@/lib/types";

let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

const getAthlete = vi.fn();
vi.mock("@/lib/api/client", () => ({
  apiClient: { getAthlete: (...args: unknown[]) => getAthlete(...args) },
}));

import { writeAthlete } from "@/components/layout/AthletePicker";
import { MaSaison } from "./MaSaison";

const ATHLETE = { id: 12, prenom: "Jean", nom: "Dupont" };

function ligne(courseId: number, rangs: Partial<Participation> = {}): Participation {
  return {
    course: { id: courseId },
    rank_overall: null,
    rank_category: null,
    rank_gender: null,
    is_pending_validation: false,
    ...rangs,
  } as unknown as Participation;
}

beforeEach(() => {
  searchParams = new URLSearchParams();
  getAthlete.mockReset();
  const stock = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (cle: string) => stock.get(cle) ?? null,
      setItem: (cle: string, valeur: string) => void stock.set(cle, valeur),
      removeItem: (cle: string) => void stock.delete(cle),
      clear: () => stock.clear(),
    },
  });
});

describe("MaSaison — état « aucun athlète retenu »", () => {
  it("ne rend rien et n'appelle pas l'API", () => {
    const { container } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    expect(container).toBeEmptyDOMElement();
    expect(getAthlete).not.toHaveBeenCalled();
  });
});

describe("MaSaison — état rempli", () => {
  beforeEach(() => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
  });

  it("met mes épreuves et mes podiums en regard du club", async () => {
    getAthlete.mockResolvedValue({
      athlete: ATHLETE,
      participations: [
        ligne(1, { rank_overall: 2 }),
        ligne(2, { rank_overall: 40 }),
        ligne(3, { rank_overall: 18 }),
        ligne(4, { rank_overall: 7 }),
      ],
    });

    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(await screen.findByText(/4 épreuves/)).toBeInTheDocument();
    expect(screen.getByText(/1 podium/)).toBeInTheDocument();
    expect(screen.getByText(/32/)).toBeInTheDocument();
  });

  it("transmet les filtres du tableau de bord à l'API", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });

    render(<MaSaison clubEvents={32} seasons="2025,2024" federalOnly={true} />);

    await waitFor(() =>
      expect(getAthlete).toHaveBeenCalledWith(12, {
        seasons: "2025,2024",
        federal_only: true,
      }),
    );
  });

  it("refetch quand la sélection de saisons change", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    await waitFor(() => expect(getAthlete).toHaveBeenCalledTimes(1));

    rerender(<MaSaison clubEvents={12} seasons="2024" federalOnly={true} />);

    await waitFor(() => expect(getAthlete).toHaveBeenCalledTimes(2));
  });

  // Même arbitrage que RankTypeToggle (#328) : le mode de rang ne change que
  // la lecture d'un champ déjà en main.
  it("ne refetch pas au changement de ?rank=, mais recompte le podium", async () => {
    getAthlete.mockResolvedValue({
      athlete: ATHLETE,
      participations: [ligne(1, { rank_overall: 40, rank_category: 2 })],
    });
    const { rerender } = render(
      <MaSaison clubEvents={32} seasons="2025" federalOnly={true} />,
    );
    expect(await screen.findByText(/0 podium/)).toBeInTheDocument();

    searchParams = new URLSearchParams("rank=category");
    rerender(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(await screen.findByText(/1 podium/)).toBeInTheDocument();
    expect(getAthlete).toHaveBeenCalledTimes(1);
  });

  it("apparaît quand l'athlète est choisi en cours de page", async () => {
    window.localStorage.removeItem("tcn-athlete");
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [ligne(1)] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
    expect(getAthlete).not.toHaveBeenCalled();

    act(() => writeAthlete(ATHLETE));

    expect(await screen.findByText(/1 épreuve/)).toBeInTheDocument();
  });
});

describe("MaSaison — états dégradés", () => {
  beforeEach(() => {
    window.localStorage.setItem("tcn-athlete", JSON.stringify(ATHLETE));
  });

  it("affiche un squelette pendant le chargement", () => {
    getAthlete.mockReturnValue(new Promise(() => {}));
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);
    expect(screen.getByTestId("ma-saison-squelette")).toBeInTheDocument();
  });

  it("propose une sortie quand ma saison est vide", async () => {
    getAthlete.mockResolvedValue({ athlete: ATHLETE, participations: [] });
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(await screen.findByText(/aucune épreuve/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ajouter un résultat/i })).toHaveAttribute(
      "href",
      "/ajouter",
    );
  });

  it("garde le nom et le lien quand le fetch échoue", async () => {
    getAthlete.mockRejectedValue(new Error("réseau"));
    render(<MaSaison clubEvents={32} seasons="2025" federalOnly={true} />);

    expect(await screen.findByText(/chiffres indisponibles/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /mon athlète/i })).toHaveAttribute(
      "href",
      "/athletes/12",
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/dashboard/MaSaison.test.tsx`
Expected: FAIL — `Failed to resolve import "./MaSaison"`.

- [ ] **Step 3: Write minimal implementation**

Ajouter dans `frontend/lib/api/client.ts`, juste avant `searchAthletes` :

```ts
// Premier appel navigateur de cette route : `/athletes/{id}` n'était jusqu'ici
// lu que par le rendu serveur de la fiche athlète. La bande « Ma saison »
// (#502) l'appelle côté client, parce que l'athlète retenu vit en
// `localStorage` et ne franchit pas la frontière serveur (#467).
getAthlete: (
  id: number,
  filters: { seasons?: string; federal_only?: boolean } = {},
) => request<AthleteDetail>(`/athletes/${id}${toQuery(filters)}`),
```

(et ajouter `AthleteDetail` à l'import de types en tête du fichier)

Créer `frontend/components/dashboard/MaSaison.tsx` :

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnnonceStatut, Card, Eyebrow } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { apiClient } from "@/lib/api/client";
import { rankTypeLabel } from "@/lib/labels";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import type { Participation } from "@/lib/types";
import { motCompte } from "@/lib/utils/format";
import { compteMaSaison } from "@/lib/utils/ma-saison";

type Etat = "chargement" | "ok" | "echec";

/** Hauteur fixe de la bande, dans ses trois états visibles.
 *
 *  La bande n'est **pas** dans le HTML initial — l'athlète retenu vit en
 *  `localStorage` et n'atteint aucun rendu serveur (`frontend/AGENTS.md:218`).
 *  Elle apparaît donc à l'hydratation, ce qui décale les compteurs club vers le
 *  bas : coût déjà assumé par #467. Ce qu'on refuse, c'est un **second**
 *  décalage au retour du fetch — d'où le squelette à la hauteur définitive. */
const HAUTEUR = 92;

/**
 * Bande « Ma saison » en tête du tableau de bord (#502, NAV-9).
 *
 * L'écran d'atterrissage ne parlait que du club en agrégat : le membre qui
 * avait désigné son nom n'y trouvait rien de lui, et le geste de choix restait
 * sans récompense. La bande met ses deux chiffres en regard de ceux du club
 * **sur la même sélection** — mêmes saisons, mêmes disciplines, même type de
 * rang, sans quoi la comparaison serait bancale.
 *
 * `?rank=` ne déclenche aucun fetch : il ne change que le champ lu dans des
 * participations déjà en main. Même arbitrage que `RankTypeToggle` (#328) et
 * qu'`EventsTable` (#489).
 */
export function MaSaison({
  clubEvents,
  seasons,
  federalOnly,
}: {
  /** Épreuves distinctes courues par le club sur la même sélection (`stats.events`). */
  clubEvents: number;
  /** Sélection de saisons en CSV — une primitive, donc une dépendance d'effet stable. */
  seasons: string;
  federalOnly: boolean | undefined;
}) {
  const athlete = useSelectedAthlete();
  const sp = useSearchParams();
  const mode = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);

  const [etat, setEtat] = useState<Etat>("chargement");
  const [participations, setParticipations] = useState<Participation[]>([]);

  const id = athlete?.id;
  useEffect(() => {
    if (id === undefined) return;
    let annule = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEtat("chargement");
    apiClient
      .getAthlete(id, { seasons, federal_only: federalOnly })
      .then((detail) => {
        if (annule) return;
        setParticipations(detail.participations);
        setEtat("ok");
      })
      .catch(() => {
        if (!annule) setEtat("echec");
      });
    return () => {
      annule = true;
    };
  }, [id, seasons, federalOnly]);

  if (!athlete) return null;

  const nom = nomComplet(athlete);
  const lienProfil = (
    <Link
      href={`/athletes/${athlete.id}`}
      className="text-sm font-semibold text-accent-ink hover:underline"
    >
      Voir mon athlète →
    </Link>
  );

  if (etat === "chargement") {
    return (
      <Bande>
        <div data-testid="ma-saison-squelette" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Skeleton className="h-6 w-72" />
          <Skeleton className="h-4 w-56" />
        </div>
      </Bande>
    );
  }

  if (etat === "echec") {
    return (
      <Bande>
        <Ligne principale={nom} secondaire="Chiffres indisponibles pour l'instant." action={lienProfil} />
      </Bande>
    );
  }

  const { epreuves, podiums } = compteMaSaison(participations, mode);
  const rang = rankTypeLabel(mode, { form: "long" });

  if (epreuves === 0) {
    const texte = `${nom} — aucune épreuve sur cette sélection.`;
    return (
      <Bande>
        <AnnonceStatut texte={`Ma saison : ${texte} Le club en a couru ${clubEvents}.`} />
        <Ligne
          principale={texte}
          secondaire={`Le club en a couru ${clubEvents}.`}
          action={
            <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
              Ajouter un résultat →
            </Link>
          }
        />
      </Bande>
    );
  }

  const principale = `${nom} — ${motCompte(epreuves, "épreuve")} · ${motCompte(podiums, "podium")} (classement ${rang})`;
  const secondaire = `Le club a couru ${motCompte(clubEvents, "épreuve")} sur la même sélection.`;

  return (
    <Bande>
      <AnnonceStatut texte={`Ma saison : ${principale}. ${secondaire}`} />
      <Ligne principale={principale} secondaire={secondaire} action={lienProfil} />
    </Bande>
  );
}

function Bande({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <Card>
        <Eyebrow>Ma saison</Eyebrow>
        <div style={{ minHeight: HAUTEUR - 24, display: "flex", alignItems: "center" }}>
          {children}
        </div>
      </Card>
    </div>
  );
}

function Ligne({
  principale,
  secondaire,
  action,
}: {
  principale: string;
  secondaire: string;
  action: React.ReactNode;
}) {
  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 20, color: "var(--tcn-ink)" }}>
          {principale}
        </div>
        <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", marginTop: 4 }}>{secondaire}</div>
      </div>
      {action}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/dashboard/MaSaison.test.tsx`
Expected: PASS (10 tests)

Puis `cd frontend && npm run lint` → clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api/client.ts frontend/components/dashboard/MaSaison.tsx frontend/components/dashboard/MaSaison.test.tsx
git commit -m "feat(502): la bande « Ma saison » et son appel client filtré"
```

---

### Task 6: Insertion dans `/dashboard`

**Files:**
- Modify: `frontend/app/(public_restricted)/dashboard/page.tsx:135-137`
- Test: `frontend/app/(public_restricted)/dashboard/page.test.tsx`

**Interfaces:**
- Consumes: `<MaSaison clubEvents seasons federalOnly />` (Task 5), `serializeSeasons(years: number[]): string` (`lib/utils/season.ts:40`).
- Produces: rien pour les tâches suivantes.

- [ ] **Step 1: Write the failing test**

Ajouter à `frontend/app/(public_restricted)/dashboard/page.test.tsx` :

```tsx
describe("bande « Ma saison » (#502)", () => {
  it("est montée au-dessus des compteurs club, avec les filtres de la page", async () => {
    const page = await DashboardPage({ searchParams: Promise.resolve({ seasons: "2025" }) });
    const rendu = JSON.stringify(page);

    expect(rendu).toContain("MaSaison");
  });

  it("n'est pas montée quand la saison du club est vide", async () => {
    // `stats.total === 0` : l'écran bascule sur l'EmptyState du club, et ma
    // saison est vide par construction.
    const page = await DashboardPage({ searchParams: Promise.resolve({ seasons: "2019" }) });
    const rendu = JSON.stringify(page);

    expect(rendu).not.toContain("MaSaison");
  });
});
```

Note pour l'implémenteur : ce fichier de test moque déjà `@/lib/api/server`. Adapter les mocks pour que `getStats` rende `total: 0` sur la saison 2019 et `total > 0` avec `events: 32` sur 2025 — lire les mocks existants en tête du fichier et suivre leur forme plutôt que d'en inventer une nouvelle. Si l'assertion sur le nom du composant sérialisé ne tient pas avec la forme des mocks en place, préférer une assertion sur la présence du composant dans l'arbre React (`page.props.children`) — mais **ne pas** rendre la page dans jsdom : c'est un composant serveur asynchrone.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: FAIL — le rendu ne contient pas `MaSaison`.

- [ ] **Step 3: Write minimal implementation**

Dans `frontend/app/(public_restricted)/dashboard/page.tsx` :

Ajouter aux imports :

```tsx
import { MaSaison } from "@/components/dashboard/MaSaison";
import { currentSeason, parseSeasonsParam, seasonAbsenceLabel, seasonSelectionLabel, serializeSeasons } from "@/lib/utils/season";
```

(la ligne `import { currentSeason, … }` existe déjà ligne 10 : y ajouter `serializeSeasons`)

Puis, dans la branche non-vide, juste après l'ouverture du fragment `<>` (ligne 135) et **avant** la grille de `StatCard` :

```tsx
{/* Au-dessus des compteurs club, à dessein (#502, NAV-9) : l'écran
    d'atterrissage ne parlait que du club en agrégat. La bande n'existe que
    pour qui a désigné son nom — elle se monte donc côté client et n'est pas
    dans le HTML initial (arbitrage #467, `frontend/AGENTS.md:218`). */}
<MaSaison
  clubEvents={stats.events}
  seasons={serializeSeasons(selected)}
  federalOnly={federal_only}
/>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run "app/(public_restricted)/dashboard/page.test.tsx"`
Expected: PASS

Puis `cd frontend && npm run build` → succès (strict TS + RSC : c'est ce qui prouve que les props passées d'un composant serveur à un composant client sont bien sérialisables).

- [ ] **Step 5: Commit**

```bash
git add "frontend/app/(public_restricted)/dashboard/page.tsx" "frontend/app/(public_restricted)/dashboard/page.test.tsx"
git commit -m "feat(502): monte la bande « Ma saison » en tête du tableau de bord"
```

---

### Task 7: Un seul nom pour l'objet — « Mon athlète »

**Files:**
- Modify: `frontend/components/layout/AthletePicker.tsx:148,154` (eyebrow et pied de modale)
- Modify: `frontend/components/layout/AppNav.tsx:553,559` (`aria-label` et tooltip de la tuile)
- Modify: `frontend/app/(public_restricted)/athletes/[id]/AthleteSelection.tsx:54` (texte du bénéfice)
- Test: `frontend/components/layout/AthletePicker.test.tsx`, `frontend/components/layout/AppNav.test.tsx`, `frontend/app/(public_restricted)/athletes/[id]/AthleteSelection.test.tsx`

**Interfaces:**
- Consumes: rien.
- Produces: rien.

**Contexte** : l'audit § 10 relève que le même objet porte **quatre noms** selon l'endroit, et que la promesse n'est énoncée nulle part. Les **verbes** ne bougent pas (« Choisir cet athlète », « Sélectionnez votre nom ») — ce sont des actions, et leur unification a déjà été faite par #323 puis #478.

- [ ] **Step 1: Write the failing test**

Dans `frontend/components/layout/AthletePicker.test.tsx` :

```tsx
describe("microcopie — un seul nom pour l'objet (#502)", () => {
  it("nomme la modale « Mon athlète »", () => {
    render(<AthletePicker onClose={() => {}} onPick={() => {}} />);
    expect(screen.getByText("Mon athlète")).toBeInTheDocument();
    expect(screen.queryByText("Accès athlète")).not.toBeInTheDocument();
  });

  // Le pied rassurait sur une inquiétude que personne n'a exprimée ; il énonce
  // désormais ce que le choix rapporte (audit § 10, gradient de but).
  it("énonce la promesse au moment du choix", () => {
    render(<AthletePicker onClose={() => {}} onPick={() => {}} />);
    expect(
      screen.getByText("Votre tableau de bord affichera vos résultats en premier."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Pas de blocage d'accès/)).not.toBeInTheDocument();
  });
});
```

Dans `frontend/app/(public_restricted)/athletes/[id]/AthleteSelection.test.tsx` :

```tsx
it("nomme le bénéfice réellement rendu par le tableau de bord (#502)", () => {
  render(<AthleteSelection athlete={ATHLETE} />);
  expect(
    screen.getByText(
      "Choisir cet athlète pour retrouver ses résultats en un geste et voir sa saison en tête du tableau de bord",
    ),
  ).toBeInTheDocument();
});
```

Dans `frontend/components/layout/AppNav.test.tsx`, ajouter au bloc qui couvre déjà la tuile de l'athlète retenu :

```tsx
it("nomme la tuile « Mon athlète » (#502)", () => {
  window.localStorage.setItem("tcn-athlete", JSON.stringify({ id: 12, prenom: "Jean", nom: "Dupont" }));
  render(<AppNav />);
  expect(screen.getByLabelText("Mon athlète — Jean Dupont")).toBeInTheDocument();
});
```

Note pour l'implémenteur : lire les mocks et helpers déjà en place en tête de `AppNav.test.tsx` (il en a plusieurs — `next/navigation`, `apiClient`) et suivre leur forme ; adapter le rendu de `<AppNav />` à la façon dont les tests existants le montent.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx components/layout/AppNav.test.tsx "app/(public_restricted)/athletes/[id]/AthleteSelection.test.tsx"`
Expected: FAIL — les anciens libellés sont encore là.

- [ ] **Step 3: Write minimal implementation**

`frontend/components/layout/AthletePicker.tsx`, dans le `<Modal>` :

```tsx
    <Modal
      eyebrow="Mon athlète"
      title="Sélectionnez votre nom"
      onClose={onClose}
      width={520}
      footer={
        <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", textAlign: "center" }}>
          Votre tableau de bord affichera vos résultats en premier.
        </div>
      }
    >
```

`frontend/components/layout/AppNav.tsx` — remplacer les deux occurrences de « Mon profil » de la tuile :

```tsx
                    aria-label={`Mon athlète — ${nomComplet(athlete)}`}
```

```tsx
              {!expanded && <TooltipContent>Mon athlète</TooltipContent>}
```

`frontend/app/(public_restricted)/athletes/[id]/AthleteSelection.tsx:54` :

```tsx
        Choisir cet athlète pour retrouver ses résultats en un geste et voir sa saison en tête du tableau de bord
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx components/layout/AppNav.test.tsx "app/(public_restricted)/athletes/[id]/AthleteSelection.test.tsx"`
Expected: PASS

Puis la suite entière : `cd frontend && npm test` → PASS, `npm run lint` → clean, `npm run build` → succès.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AthletePicker.tsx frontend/components/layout/AthletePicker.test.tsx frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx "frontend/app/(public_restricted)/athletes/[id]/AthleteSelection.tsx" "frontend/app/(public_restricted)/athletes/[id]/AthleteSelection.test.tsx"
git commit -m "feat(502): un seul nom pour l'objet, et la promesse énoncée au moment du choix"
```

---

### Task 8: Consigner l'arbitrage dans `frontend/AGENTS.md`

**Files:**
- Modify: `frontend/AGENTS.md:218-245` (la puce de l'arbitrage #467)

**Interfaces:**
- Consumes: rien.
- Produces: rien.

**Pourquoi une tâche à part** : la puce annonce l'arbitrage comme valable « aussi pour #502, #503, #504 ». #502 est le premier lot à le consommer réellement ; la puce doit dire ce que ça a donné, sinon le lot suivant repart de l'hypothèse au lieu du constat.

- [ ] **Step 1: Compléter la puce existante**

Ajouter, à la fin de la puce « L'athlète retenu ne franchit pas la frontière serveur » (juste après le paragraphe « Le prix, assumé : … de la mise en avant, non. ») :

```markdown
  **Constaté sur #502**, premier consommateur réel de l'arbitrage : la bande
  « Ma saison » lit le stock par `useSelectedAthlete()` — pendant de
  `useIsSelectedAthlete`, ajouté à côté de lui — puis appelle
  `apiClient.getAthlete(id, { seasons, federal_only })`. C'est le **premier
  appel navigateur** de `/athletes/{id}`, jusque-là lue par le seul rendu
  serveur de la fiche athlète ; les deux filtres y ont été ajoutés
  **optionnels et neutres par défaut**, pour que « mes » chiffres se comptent
  sur exactement la même base que ceux du club rendus au-dessus. Le besoin
  serveur qui aurait rouvert l'arbitrage n'est donc pas apparu : le filtrage
  est passé dans la requête, pas dans le rendu, et `/dashboard` garde sa
  fenêtre de revalidation de 30 s partagée entre tous les visiteurs.

  Deux règles s'attrapent en passant, valables pour #503 et #504 : le podium
  d'un athlète doit se calculer sur le **même `?rank=`** que les compteurs
  club (`lib/utils/ma-saison.ts`, miroir de `stats_service._rank_counters`),
  et un bloc client monté au-dessus de contenu serveur réserve sa hauteur dès
  l'hydratation — sinon le retour du fetch ajoute un **second** décalage au
  premier.
```

- [ ] **Step 2: Vérifier**

Run: `cd frontend && npx vitest run test/` — aucun test ne lit ce fichier, la vérification est une relecture : les numéros de ligne cités ailleurs dans `AGENTS.md` ne doivent pas avoir été invalidés par l'insertion.

- [ ] **Step 3: Commit**

```bash
git add frontend/AGENTS.md
git commit -m "docs(502): ce que le premier consommateur de l'arbitrage #467 a donné"
```

---

## Fin de branche

Commune aux trois voies du workflow (`AGENTS.md` racine), et **déclenchée par l'utilisateur**, pas par l'exécuteur :

1. `superpowers:requesting-code-review`
2. Le sous-agent `ui-ux-review` — la branche touche `frontend/`. Lecture seule ; il juge du rendu et ne rouvre jamais l'identité visuelle.
3. `superpowers:verification-before-completion`
4. `superpowers:finishing-a-development-branch`

La PR lie l'issue par un mot-clé **anglais** : `Closes #502`. Le reste de la description est en français.

## Self-review du plan

**Couverture de la spec** — chaque section du design a sa tâche :

| Section du design | Tâche |
| --- | --- |
| Contrat de données — backend | 1 (repository) + 2 (route) |
| Le calcul — côté client (tableau des 4 modes) | 3 |
| Le composant — lecture du stock | 4 |
| Le composant — fetch, rendu, 4 états | 5 |
| Insertion dans `/dashboard` + `AnnonceStatut` | 5 (annonce) + 6 (insertion) |
| Microcopie — un seul nom | 7 |
| Tests backend (5 cas) | 1 + 2 |
| Tests frontend (4 familles) | 3, 4, 5, 7 |
| Décision « décalage à l'hydratation » | 5 (`HAUTEUR`, squelette) |
| Décision « épreuves = courses distinctes » | 3 (test dédié) |
| Décision « exclusion des pendantes » | 3 (test dédié) |

Ajouté hors design : **Task 8**, qui consigne l'arbitrage consommé dans `frontend/AGENTS.md` — le design le supposait acquis sans dire qui l'écrirait.

**Cohérence des types entre tâches** — `seasons` est une **chaîne CSV** de bout en bout : prop de `MaSaison` (Task 5), argument de `apiClient.getAthlete` (Task 5), `serializeSeasons(selected)` à l'appel (Task 6), `parse_seasons(seasons)` côté route (Task 2). Le seul endroit où c'est une `list[int]` est sous `parse_seasons`, dans le repository (Task 1). `compteMaSaison` rend `{ epreuves, podiums }` — sans accent sur `epreuves`, identique en Task 3 et Task 5.
