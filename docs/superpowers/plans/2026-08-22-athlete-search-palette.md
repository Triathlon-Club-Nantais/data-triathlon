# NAV-8 — Palette de recherche d'athlète, implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les cinq défauts de la palette `⌘K` (`AthletePicker`/`Modal`)
relevés par `NAV-8` (#484) : squelette de chargement, `listbox` accessible au
clavier, focus piégé/restauré, classement par pertinence servi par une route
backend dédiée qui interroge les athlètes plutôt que d'agréger des
participations côté client.

**Architecture:** Nouvel endpoint `GET /athletes/search` (couche
`api → services non nécessaires ici → repositories → DB`, pas de couche
service : la logique de classement est un détail de requête SQL, elle vit dans
le repository comme `search_admin`) qui rend des `AthleteSearchResult` triés
par pertinence puis volume. Le front bascule `AthletePicker` sur ce nouvel
appel (au lieu d'agréger `/participations` côté client), puis réécrit son
rendu en `listbox` ARIA avec squelette de chargement ; `Modal` (`components/tcn/`)
gagne un piège de focus générique, profitant à ses deux consommateurs.

**Tech Stack:** Backend Python 3.13 / FastAPI / SQLAlchemy 2.0 / pytest.
Frontend Next.js 16 / TypeScript / Vitest + React Testing Library. Aucune
nouvelle dépendance.

**Spec:** `docs/superpowers/specs/2026-08-22-athlete-search-palette-design.md`
(design complet, arbitrages backend et bibliothèque frontend justifiés — les
tâches ci-dessous l'implémentent, elles ne le re-justifient pas).

## Global Constraints

- Identité arbitrée intacte : aucun token `--tcn-*`, aucune police, aucun
  dégradé ne change (contrainte #325).
- Frontière `components/tcn/` vs `components/ui/` non rejugée : aucune
  nouvelle primitive dans l'une ou l'autre, tout le nouveau markup ARIA vit
  directement dans `AthletePicker.tsx` (design § 3.2).
- `GET /athletes` existant n'est ni modifié ni retiré ; la nouvelle route est
  `GET /athletes/search`, distincte (design § 3.1).
- Le stock `localStorage` de l'athlète retenu, `useIsSelectedAthlete` et
  `ATHLETE_CHANGED_EVENT` (#467) restent inchangés — ce lot ne touche pas au
  dispositif « athlète retenu ».
- TDD non négociable (Principe III) : chaque tâche commence par un test qui
  échoue.
- Pas de compatibilité ascendante à préserver côté code interne : la logique
  d'agrégation client (100 participations → 12 athlètes, tri par volume) est
  **supprimée**, pas gardée en repli.
- Backend : tests unitaires sans réseau (`uv run pytest -m "not integration"`,
  depuis `backend/`). Frontend : `npm test` (Vitest), depuis `frontend/`.

---

## File Structure

| Fichier | Rôle |
| --- | --- |
| `backend/app/repositories/athlete_repository.py` | Ajoute `_escape_like` (extrait de `name_filter`), `_relevance_rank`, `search_by_relevance` |
| `backend/tests/test_repositories/test_athlete_repository.py` | Tests de `search_by_relevance` |
| `backend/app/schemas/athlete.py` | Ajoute `AthleteSearchResult` |
| `backend/app/api/v1/athletes.py` | Ajoute la route `GET /athletes/search` |
| `backend/tests/test_api/test_athletes_api.py` | Tests de la route |
| `frontend/lib/types.ts` | Ajoute l'interface `AthleteSearchResult` |
| `frontend/lib/api/client.ts` | Ajoute `apiClient.searchAthletes` |
| `frontend/components/layout/AthletePicker.tsx` | Bascule de source de données, squelette, `listbox` ARIA |
| `frontend/components/layout/AthletePicker.test.tsx` | Tests réécrits/étendus |
| `frontend/components/tcn/Modal.tsx` | Piège + restauration du focus |
| `frontend/components/tcn/Modal.test.tsx` | Nouveau fichier de tests |

---

### Task 1: Backend — `athlete_repository.search_by_relevance`

**Files:**
- Modify: `backend/app/repositories/athlete_repository.py`
- Test: `backend/tests/test_repositories/test_athlete_repository.py`

**Interfaces:**
- Consumes: `Athlete`, `Participation` (modèles existants), `name_filter`,
  `tcn_clause` (`app/core/club.py`), `deaccent` (`app/core/text.py`) — tous
  déjà importés dans ce fichier.
- Produces: `search_by_relevance(db, *, term: str, club_only: bool = False, limit: int = 12) -> list[tuple[Athlete, int]]`
  — consommée par la Task 2.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter en fin de `backend/tests/test_repositories/test_athlete_repository.py` :

```python
def test_search_by_relevance_classe_prefixe_avant_sous_chaine_malgre_le_volume(db_session):
    """Preuve de terrain NAV-8 (audit § 5) : un préfixe exact bat toujours une
    sous-chaîne en milieu de nom, quel que soit le volume de courses."""
    prefixe = athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Mathieu")
    milieu = athlete_repository.get_or_create(db_session, nom="CHERRUEAU", prenom="Yves")
    db_session.flush()
    _inscrit(db_session, prefixe, _epreuve(db_session, "P1"), "1")
    for i in range(5):
        _inscrit(db_session, milieu, _epreuve(db_session, f"P-milieu-{i}"), "1")
    db_session.commit()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr")

    assert [a.nom for a, _ in resultats] == ["HERRMANN", "CHERRUEAU"]


def test_search_by_relevance_classe_les_trois_paliers(db_session):
    """0 = préfixe exact, 1 = début de mot (après espace/trait d'union), 2 = sous-chaîne."""
    prefixe = athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Anna")
    debut_mot = athlete_repository.get_or_create(db_session, nom="DUBOIS-HERRY", prenom="Alex")
    sous_chaine = athlete_repository.get_or_create(db_session, nom="CHERRUEAU", prenom="Yves")
    db_session.flush()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr")

    assert [a.nom for a, _ in resultats] == ["HERRMANN", "DUBOIS-HERRY", "CHERRUEAU"]


def test_search_by_relevance_departage_par_volume_dans_un_meme_palier(db_session):
    """Deux préfixes exacts : le volume reste le départage à l'intérieur d'un
    même palier — « avant le volume » ne s'applique qu'entre paliers différents."""
    peu_couru = athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Mathieu")
    tres_couru = athlete_repository.get_or_create(db_session, nom="HERRY", prenom="Yves")
    db_session.flush()
    _inscrit(db_session, peu_couru, _epreuve(db_session, "P1"), "1")
    for i in range(5):
        _inscrit(db_session, tres_couru, _epreuve(db_session, f"P-herry-{i}"), "1")
    db_session.commit()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr")

    assert [a.nom for a, _ in resultats] == ["HERRY", "HERRMANN"]


def test_search_by_relevance_respecte_club_only(db_session):
    membre = athlete_repository.get_or_create(
        db_session, nom="HERRMANN", prenom="Mathieu", club="Triathlon Club Nantais"
    )
    exterieur = athlete_repository.get_or_create(
        db_session, nom="HERRY", prenom="Yves", club="Un Autre Club"
    )
    db_session.flush()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr", club_only=True)

    assert [a.nom for a, _ in resultats] == ["HERRMANN"]


def test_search_by_relevance_respecte_la_limite(db_session):
    for i in range(3):
        athlete_repository.get_or_create(db_session, nom=f"HERR{i}", prenom="A")
    db_session.flush()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr", limit=2)

    assert len(resultats) == 2
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py -k search_by_relevance -v`
Expected: FAIL — `AttributeError: module 'athlete_repository' has no attribute 'search_by_relevance'`

- [ ] **Step 3: Extraire `_escape_like` de `name_filter` (refactor sans changement de comportement)**

Dans `backend/app/repositories/athlete_repository.py`, remplacer le corps de
`name_filter` :

```python
def _escape_like(word: str) -> str:
    """Échappe les jokers `LIKE` (`\\`, `%`, `_`) d'un terme utilisateur.

    Extrait de `name_filter` (#484) pour être réutilisé par le classement de
    pertinence de `search_by_relevance` sans dupliquer l'échappement.
    """
    for joker in ("\\", "%", "_"):
        word = word.replace(joker, f"\\{joker}")
    return word


def name_filter(term: str):
    """Filtre nom **ou** prénom d'athlète, mot à mot, sans casse ni accents.
    ...
    """
    clauses = []
    for word in deaccent(term).split():
        word = _escape_like(word)
        pattern = f"%{word.lower()}%"
        clauses.append(
            or_(
                func.unaccent(func.lower(Athlete.nom)).like(pattern, escape="\\"),
                func.unaccent(func.lower(Athlete.prenom)).like(pattern, escape="\\"),
            )
        )
    if not clauses:
        return false()
    return and_(*clauses)
```

(Le docstring existant de `name_filter` est conservé tel quel — seul le corps
change, en gardant le comportement identique.)

- [ ] **Step 4: Lancer les tests existants de `name_filter`/`search` pour vérifier qu'aucune régression n'est introduite**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py -k "search_by_name or search_par or search_avec_terme" -v`
Expected: PASS (comportement inchangé)

- [ ] **Step 5: Implémenter `_relevance_rank` et `search_by_relevance`**

Ajouter à la fin de `backend/app/repositories/athlete_repository.py` :

```python
def _relevance_rank(term: str):
    """Palier de pertinence pour `search_by_relevance` (#484) : 0 = préfixe
    exact, 1 = début de mot après un espace ou un trait d'union, 2 = sous-chaîne
    (déjà tout ce que `name_filter` matchait, sans distinction).

    Combine les conditions sur `nom` et `prenom` en un seul `case()` — évite de
    calculer un rang par champ puis un `LEAST`, absent de SQLite (mesuré : voir
    le design). `min(rang_nom, rang_prenom)` équivaut à « le palier le plus bas
    est atteint si l'une des deux conditions du palier l'est ».
    """
    t = _escape_like(deaccent(term).lower())
    nom = func.unaccent(func.lower(Athlete.nom))
    prenom = func.unaccent(func.lower(Athlete.prenom))
    prefixe = or_(nom.like(f"{t}%", escape="\\"), prenom.like(f"{t}%", escape="\\"))
    debut_mot = or_(
        nom.like(f"% {t}%", escape="\\"),
        nom.like(f"%-{t}%", escape="\\"),
        prenom.like(f"% {t}%", escape="\\"),
        prenom.like(f"%-{t}%", escape="\\"),
    )
    return case((prefixe, 0), (debut_mot, 1), else_=2)


def search_by_relevance(
    db: Session, *, term: str, club_only: bool = False, limit: int = 12
) -> list[tuple[Athlete, int]]:
    """Classement pour la palette `⌘K` (#484, NAV-8) : pertinence puis volume.

    À la différence de `search`/`search_admin` (ordonnées `nom, prenom`), le
    tri ici est `_relevance_rank` puis le nombre de participations décroissant
    — le volume ne départage plus qu'à l'intérieur d'un même palier de
    pertinence, jamais entre deux paliers différents.
    """
    compte = func.count(Participation.id)
    rang = _relevance_rank(term)
    requete = (
        db.query(Athlete, compte)
        .outerjoin(Participation, Participation.athlete_id == Athlete.id)
        .filter(name_filter(term))
        .group_by(Athlete.id)
    )
    if club_only:
        requete = requete.filter(tcn_clause(Athlete.club))
    return (
        requete.order_by(rang, compte.desc(), Athlete.nom, Athlete.prenom)
        .limit(limit)
        .all()
    )
```

- [ ] **Step 6: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py -k search_by_relevance -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Lancer toute la suite du fichier pour vérifier l'absence de régression**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py -v`
Expected: PASS (tous les tests, existants et nouveaux)

- [ ] **Step 8: Commit**

```bash
git add backend/app/repositories/athlete_repository.py backend/tests/test_repositories/test_athlete_repository.py
git commit -m "feat(backend): rank athlete search by relevance, not just volume

Extracts the LIKE-escaping from name_filter into _escape_like and adds
search_by_relevance: exact-prefix, then word-start, then substring —
volume only tiebreaks inside a tier. Portable SQL (no LEAST, absent on
SQLite): a single CASE combines the nom/prenom conditions per tier.

Refs #484"
```

---

### Task 2: Backend — route `GET /athletes/search`

**Files:**
- Modify: `backend/app/schemas/athlete.py`
- Modify: `backend/app/api/v1/athletes.py`
- Test: `backend/tests/test_api/test_athletes_api.py`

**Interfaces:**
- Consumes: `athlete_repository.search_by_relevance` (Task 1),
  `AthleteBrief` (schema existant), `is_club_scope` (`app/core/club.py`,
  déjà importé dans `athletes.py`).
- Produces: `AthleteSearchResult` (schema, champs de `AthleteBrief` +
  `participation_count: int`) ; route `GET /athletes/search` — consommés par
  la Task 3 côté front.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter en fin de `backend/tests/test_api/test_athletes_api.py` :

```python
# ── GET /athletes/search (issue #484, NAV-8) ─────────────────────────────────


def test_search_rend_le_compte_de_participations_sans_date_de_naissance(client, db_session):
    from app.repositories import athlete_repository

    course = _epreuve(db_session, "Recherche")
    athlete = athlete_repository.get_or_create(
        db_session, nom="HERRMANN", prenom="Mathieu", birth_date=date(1990, 1, 1), club="TCN"
    )
    db_session.commit()
    _inscrit(db_session, athlete, course, "1")

    resp = client.get("/api/v1/athletes/search", params={"q": "herr"})

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["nom"] == "HERRMANN"
    assert body[0]["participation_count"] == 1
    assert "birth_date" not in body[0]


def test_search_classe_par_pertinence_avant_le_volume(client, db_session):
    """Preuve de terrain NAV-8 (audit § 5) rejouée à l'API."""
    from app.repositories import athlete_repository

    prefixe = athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Mathieu")
    milieu = athlete_repository.get_or_create(db_session, nom="CHERRUEAU", prenom="Yves")
    db_session.commit()
    _inscrit(db_session, prefixe, _epreuve(db_session, "P1"), "1")
    for i in range(5):
        _inscrit(db_session, milieu, _epreuve(db_session, f"P-milieu-{i}"), "1")

    resp = client.get("/api/v1/athletes/search", params={"q": "herr"})

    assert [a["nom"] for a in resp.json()] == ["HERRMANN", "CHERRUEAU"]


def test_search_refuse_un_terme_de_moins_de_deux_caracteres(client):
    resp = client.get("/api/v1/athletes/search", params={"q": "h"})
    assert resp.status_code == 422


def test_search_refuse_l_absence_de_terme(client):
    resp = client.get("/api/v1/athletes/search")
    assert resp.status_code == 422


def test_search_respecte_la_limite(client, db_session):
    from app.repositories import athlete_repository

    for i in range(3):
        athlete_repository.get_or_create(db_session, nom=f"TESTLIM{i}", prenom="A")
    db_session.commit()

    resp = client.get("/api/v1/athletes/search", params={"q": "testlim", "limit": 2})

    assert len(resp.json()) == 2


def test_search_nest_pas_capturee_par_la_route_athlete_id(client, db_session):
    """Précédence de route, même piège que `/athletes/season-activity` (#274) :
    `search` doit se résoudre avant `{athlete_id}` (int), sinon FastAPI rend
    422 sur `search` comme identifiant invalide."""
    resp = client.get("/api/v1/athletes/search", params={"q": "zzzzz"})
    assert resp.status_code == 200
    assert resp.json() == []
```

`_epreuve`/`_inscrit` sont déjà définies en tête de
`test_athletes_api.py` (section `/athletes/season-activity`, lignes 65-82) —
ne pas les redéfinir.

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_api/test_athletes_api.py -k search -v`
Expected: FAIL — 404 (route inexistante) sur chaque test.

- [ ] **Step 3: Ajouter le schéma `AthleteSearchResult`**

Dans `backend/app/schemas/athlete.py`, ajouter après `AthleteBrief` :

```python
class AthleteSearchResult(AthleteBrief):
    """Résultat de `GET /athletes/search` (#484) : `AthleteBrief` + le compte
    de participations qu'affiche la palette `⌘K` sous le nom. Pas de
    `birth_date` — cette route reste publique, la date de naissance reste
    réservée à `athletes:read` (voir `athlete_repository.search_admin`)."""

    participation_count: int
```

- [ ] **Step 4: Ajouter la route, avant `GET /athletes/{athlete_id}`**

Dans `backend/app/api/v1/athletes.py`, modifier l'import et ajouter la route
juste avant `get_athlete` (donc après `list_athletes_season_activity`, sur le
même besoin de précédence que celle-ci) :

```python
from app.schemas.athlete import AthleteBrief, AthleteSearchResult, AthleteSeasonActivity
```

```python
# Déclarée avant `/athletes/{athlete_id}`, même raison que
# `/athletes/season-activity` ci-dessus (#484).
@router.get("/athletes/search", response_model=list[AthleteSearchResult])
def search_athletes(
    q: str = Query(..., min_length=2),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Recherche classée par pertinence pour la palette `⌘K` (#484, NAV-8).

    Distincte de `GET /athletes` : celle-ci trie par pertinence (préfixe
    exact, début de mot, sous-chaîne) puis volume, et rend le compte de
    participations — deux choses que `GET /athletes` ne fait pas et n'a pas à
    faire pour ses propres appelants.
    """
    lignes = athlete_repository.search_by_relevance(
        db, term=q, club_only=is_club_scope(scope), limit=limit
    )
    return [
        AthleteSearchResult(
            **AthleteBrief.model_validate(athlete).model_dump(), participation_count=nombre
        )
        for athlete, nombre in lignes
    ]
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_api/test_athletes_api.py -k search -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Lancer la suite complète de la garde site pour confirmer que la nouvelle route en hérite automatiquement**

Run: `cd backend && uv run pytest tests/test_auth/test_site_access_gate.py -v`
Expected: PASS — `GET /athletes/search` apparaît dans l'inventaire auto-découvert
(`_routes_gardees_par_le_site`, dérivé de `app.openapi()`) et
`test_toute_route_gardee_refuse_l_anonyme` la couvre sans modification de ce
fichier.

- [ ] **Step 7: Lancer toute la suite backend non-réseau**

Run: `cd backend && uv run pytest -m "not integration"`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/athlete.py backend/app/api/v1/athletes.py backend/tests/test_api/test_athletes_api.py
git commit -m "feat(backend): add GET /athletes/search for the command palette

New route, additive to the /api/v1 contract (GET /athletes is untouched):
relevance-ranked, capped, with a participation_count the picker needs
and GET /athletes doesn't return. Declared before /athletes/{id}, same
precedence pitfall as /athletes/season-activity.

Refs #484"
```

---

### Task 3: Frontend — `AthletePicker` interroge `/athletes/search` (corrige les défauts 4 et 5)

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/components/layout/AthletePicker.tsx`
- Modify: `frontend/components/layout/AthletePicker.test.tsx`

**Interfaces:**
- Consumes: rien de nouveau côté backend au-delà de la Task 2 (le mock du
  test ne dépend pas du serveur réel).
- Produces: `apiClient.searchAthletes(q: string, limit?: number): Promise<AthleteSearchResult[]>` ;
  `AthletePicker` garde `rows: AthleteSearchResult[]` en état — consommé par
  les Tasks 5 et 6.

- [ ] **Step 1: Écrire/adapter les tests qui échouent**

Dans `frontend/components/layout/AthletePicker.test.tsx`, remplacer le mock
en tête de fichier :

```tsx
const searchAthletes = vi.fn();
vi.mock("@/lib/api/client", () => ({
  apiClient: { searchAthletes: (q: string, limit?: number) => searchAthletes(q, limit) },
}));
```

Dans le describe `"AthletePicker — aucune correspondance (ETAT-3)"`, remplacer
`listParticipations.mockResolvedValue([]);` par
`searchAthletes.mockResolvedValue([]);`.

Ajouter un nouveau describe à la fin du fichier :

```tsx
describe("AthletePicker — classement par pertinence, servi par l'API (NAV-8, #484)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("affiche les résultats dans l'ordre rendu par l'API, sans les retrier par volume", async () => {
    searchAthletes.mockResolvedValue([
      { id: 1, nom: "HERRMANN", prenom: "Mathieu", gender: "", club: "TCN", participation_count: 3 },
      { id: 2, nom: "HERRY", prenom: "Yves", gender: "", club: "TCN", participation_count: 5 },
    ]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Rechercher un nom…"), "herr");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    const noms = (await screen.findAllByText(/Mathieu HERRMANN|Yves HERRY/)).map(
      (el) => el.textContent,
    );
    expect(noms).toEqual(["Mathieu HERRMANN", "Yves HERRY"]);
    expect(searchAthletes).toHaveBeenCalledWith("herr", 13);
  });

  it("affiche le nombre de participations rendu par l'API", async () => {
    searchAthletes.mockResolvedValue([
      { id: 1, nom: "GAUDIN", prenom: "Marie", gender: "", club: "TCN", participation_count: 3 },
    ]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Rechercher un nom…"), "gaudin");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(await screen.findByText(/3 épreuves/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx`
Expected: FAIL — `AthletePicker` appelle encore `apiClient.listParticipations`,
jamais `searchAthletes` ; le mock n'est jamais déclenché, les assertions sur le
texte échouent (timeout `findAllByText`/`findByText`).

- [ ] **Step 3: Ajouter le type `AthleteSearchResult`**

Dans `frontend/lib/types.ts`, ajouter après `AthleteSeasonActivity` (ligne 19) :

```ts
// Miroir de AthleteSearchResult backend (#484) — recherche classée par
// pertinence pour la palette ⌘K. `club` en plus de AthleteSeasonActivity :
// affiché sous le nom dans la palette, comme `AthleteBrief.club` l'était déjà.
export interface AthleteSearchResult {
  id: number;
  nom: string;
  prenom: string;
  gender: string;
  club: string | null;
  participation_count: number;
}
```

- [ ] **Step 4: Ajouter `apiClient.searchAthletes`**

Dans `frontend/lib/api/client.ts` :
- Ajouter `AthleteSearchResult` à la liste des types importés (ordre
  alphabétique, juste après `AthleteBrief`).
- Ajouter la méthode juste après `listParticipations` (ligne 145) :

```ts
  // Palette ⌘K (#484) — distincte de `listParticipations` : interroge les
  // athlètes directement (classés par pertinence côté backend), plus
  // l'agrégation de participations plafonnée à 100 lignes qui pouvait faire
  // disparaître un athlète peu couru sur un patronyme fréquent.
  searchAthletes: (q: string, limit = 13) =>
    request<AthleteSearchResult[]>(`/athletes/search${toQuery({ q, limit })}`),
```

- [ ] **Step 5: Basculer `AthletePicker` sur la nouvelle source de données**

Dans `frontend/components/layout/AthletePicker.tsx` :

Remplacer l'import :
```tsx
import type { AthleteSearchResult } from "@/lib/types";
```
(retire l'import de `AthleteBrief`, qui n'était utilisé que par `AthleteRow`)

Retirer entièrement le type alias :
```tsx
type AthleteRow = AthleteBrief & { count: number };
```

Ajouter une constante de module, juste avant `AthletePicker` :
```tsx
/** Nombre d'athlètes affichés — au-delà, la palette précise « trop de
 *  résultats » plutôt que d'en cacher silencieusement (défaut 4/5, #484). */
const PAGE_SIZE = 12;
```

Remplacer l'état et l'effet de recherche :
```tsx
  const [rows, setRows] = useState<AthleteSearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRows([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const found = await apiClient.searchAthletes(q, PAGE_SIZE + 1);
        if (!cancelled) setRows(found);
      } catch {
        if (!cancelled) setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query]);
```

Dans le rendu, remplacer `{rows.map((a) => {` par
`{rows.slice(0, PAGE_SIZE).map((a) => {` et, dans le corps de la ligne,
remplacer l'affichage du compte :
```tsx
                <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>
                  {a.club ?? "Sans club"} · {a.participation_count} épreuve
                  {a.participation_count > 1 ? "s" : ""}
                </div>
```

(« épreuve », pas « course » : #478/COPY-1, `frontend/AGENTS.md` — c'est le
seul mot que l'utilisateur doit lire pour cet objet, `course` restant réservé
à l'identifiant technique. La ligne d'origine du fichier dit déjà « épreuve »
depuis #478 ; ne pas la faire régresser vers « course ».)

(`rows.length` peut valoir jusqu'à `PAGE_SIZE + 1` — le `slice` borne le rendu
à 12 dès cette tâche ; la Task 6 utilisera `rows.length > PAGE_SIZE` pour
afficher la précision « trop de résultats » sans nouvel appel réseau.)

- [ ] **Step 6: Lancer les tests pour vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx`
Expected: PASS (tous les tests du fichier, existants et nouveaux)

- [ ] **Step 7: Lancer le typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (aucune référence résiduelle à `AthleteRow`/`AthleteBrief` dans ce fichier)

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/components/layout/AthletePicker.tsx frontend/components/layout/AthletePicker.test.tsx
git commit -m "fix(frontend): search athletes directly instead of aggregating participations

AthletePicker queried /participations (100 rows max) and aggregated
client-side, which could drop an infrequent athlete on a common
surname and always sorted by volume. It now calls the new
GET /athletes/search, which ranks server-side and returns the athlete
directly — no client-side re-sort, no 100-row cap.

Refs #484"
```

---

### Task 4: Frontend — `Modal` piège et restaure le focus

**Files:**
- Modify: `frontend/components/tcn/Modal.tsx`
- Test: `frontend/components/tcn/Modal.test.tsx` (nouveau)

**Interfaces:**
- Consumes: rien de nouveau — `Modal(props)` garde exactement la même
  signature publique.
- Produces: comportement de focus, consommé implicitement par tous les
  appelants de `Modal` (`AthletePicker`, `CourseSourcesPanel`) sans
  changement de leur code.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `frontend/components/tcn/Modal.test.tsx` :

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./Modal";

function Scenario({ onClose }: { onClose: () => void }) {
  return (
    <div>
      <button type="button">Ouvrir</button>
      <Modal title="Titre" onClose={onClose}>
        <button type="button">Premier</button>
        <button type="button">Dernier</button>
      </Modal>
    </div>
  );
}

describe("Modal — piège et restauration du focus (NAV-8, #484)", () => {
  it("piège le focus : Tab depuis le dernier élément revient au premier", async () => {
    const user = userEvent.setup();
    render(<Scenario onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Dernier" }));
    await user.tab();

    expect(screen.getByRole("button", { name: "Fermer" })).toHaveFocus();
  });

  it("piège le focus : Shift+Tab depuis le premier élément va au dernier", async () => {
    const user = userEvent.setup();
    render(<Scenario onClose={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Fermer" }));
    await user.tab({ shift: true });

    expect(screen.getByRole("button", { name: "Dernier" })).toHaveFocus();
  });

  it("restaure le focus sur le déclencheur à la fermeture", async () => {
    const user = userEvent.setup();
    const ouvrir = document.createElement("button");
    ouvrir.textContent = "Ouvrir";
    document.body.appendChild(ouvrir);
    ouvrir.focus();

    const { unmount } = render(<Modal title="Titre" onClose={vi.fn()} />);
    expect(ouvrir).not.toHaveFocus();

    unmount();

    expect(ouvrir).toHaveFocus();
    document.body.removeChild(ouvrir);
    void user;
  });
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/tcn/Modal.test.tsx`
Expected: FAIL — les trois tests (aucun piège de focus ni restauration
aujourd'hui).

- [ ] **Step 3: Implémenter le piège et la restauration de focus**

Remplacer le contenu de `frontend/components/tcn/Modal.tsx` :

```tsx
"use client";
import { useEffect, useId, useRef, type CSSProperties, type ReactNode } from "react";
import { IconButton } from "./IconButton";
import { Eyebrow } from "./Eyebrow";

/** Dialogue centré sur scrim encre flouté (eyebrow + titre Anton + fermeture). */
export function Modal({
  open = true,
  eyebrow,
  title,
  onClose = () => {},
  footer = null,
  width = 520,
  children,
  style,
}: {
  open?: boolean;
  eyebrow?: ReactNode;
  title?: ReactNode;
  onClose?: () => void;
  footer?: ReactNode;
  width?: number;
  children?: ReactNode;
  style?: CSSProperties;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);

  // Mémorise le déclencheur à l'ouverture, lui rend le focus à la fermeture
  // (démontage, ou passage à `open=false`) — défaut 3 de NAV-8 (#484).
  useEffect(() => {
    if (!open) return;
    const declencheur =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    return () => {
      declencheur?.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;
      const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const premier = focusables[0];
      const dernier = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === premier) {
        e.preventDefault();
        dernier.focus();
      } else if (!e.shiftKey && document.activeElement === dernier) {
        e.preventDefault();
        premier.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--tcn-overlay)",
        backdropFilter: "blur(3px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        onClick={(e) => e.stopPropagation()}
        style={{
          width,
          maxWidth: "calc(100vw - 32px)",
          maxHeight: "82vh",
          display: "flex",
          flexDirection: "column",
          background: "var(--tcn-surface)",
          borderRadius: "var(--tcn-radius-modal)",
          boxShadow: "var(--tcn-shadow-modal)",
          overflow: "hidden",
          ...style,
        }}
      >
        <div style={{ padding: "24px 28px 18px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div>
            {eyebrow ? <Eyebrow style={{ fontSize: 12 }}>{eyebrow}</Eyebrow> : null}
            <div id={titleId} style={{ fontFamily: "var(--tcn-font-display)", fontSize: 26, color: "var(--tcn-ink)", marginTop: eyebrow ? 4 : 0 }}>
              {title}
            </div>
          </div>
          <IconButton variant="close" onClick={onClose} aria-label="Fermer">×</IconButton>
        </div>

        <div style={{ overflowY: "auto", padding: "22px 28px 26px" }}>{children}</div>

        {footer ? <div style={{ padding: "16px 28px", borderTop: "1px solid var(--tcn-border)" }}>{footer}</div> : null}
      </div>
    </div>
  );
}
```

(Seuls changent : les deux `useEffect` — le premier nouveau pour la
mémorisation/restauration, le second étend celui d'`Escape` existant avec le
piège `Tab` — et `dialogRef` posé sur le conteneur `role="dialog"`. Le reste
du fichier est identique à l'original.)

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/tcn/Modal.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Lancer les suites des deux consommateurs pour confirmer l'absence de régression**

Run: `cd frontend && npx vitest run components/layout/AppNav.test.tsx components/courses/CourseSourcesPanel.test.tsx components/layout/AthletePicker.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/components/tcn/Modal.tsx frontend/components/tcn/Modal.test.tsx
git commit -m "fix(a11y): trap and restore focus in Modal

Escape already closed the dialog; Tab could still walk focus out of
it, and closing never gave focus back to whatever opened it. Both
AthletePicker and CourseSourcesPanel go through Modal, so both are
fixed by this one change.

Refs #484"
```

---

### Task 5: Frontend — squelette de chargement dans `AthletePicker`

**Files:**
- Modify: `frontend/components/layout/AthletePicker.tsx`
- Modify: `frontend/components/layout/AthletePicker.test.tsx`

**Interfaces:**
- Consumes: `Skeleton` de `frontend/components/ui/skeleton.tsx` (déjà utilisé
  par les `loading.tsx` de routes récentes — même composant, même import).
- Produces: rien de nouveau consommé par une tâche suivante — le rendu du
  squelette est un état terminal de la Task 6 (qui ajoute la `listbox`
  au-dessous, pas au-dessus, du même bloc conditionnel).

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter au describe `"AthletePicker — classement par pertinence…"` (ou un
nouveau describe) de `AthletePicker.test.tsx` :

```tsx
describe("AthletePicker — squelette pendant le chargement (ETAT-2, #484)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("affiche un squelette pendant les 250 ms de debounce et le temps réseau", async () => {
    let resoudre: (v: unknown[]) => void = () => {};
    searchAthletes.mockReturnValue(
      new Promise((resolve) => {
        resoudre = resolve;
      }),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Rechercher un nom…"), "gaudin");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
    expect(screen.queryByText("Aucun athlète trouvé")).not.toBeInTheDocument();

    await act(async () => {
      resoudre([]);
    });
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx -t "squelette"`
Expected: FAIL — aucun `[data-slot="skeleton"]` rendu aujourd'hui pendant
`loading` (la zone est vide, cf. défaut 1).

- [ ] **Step 3: Implémenter le squelette**

Dans `frontend/components/layout/AthletePicker.tsx`, ajouter l'import :

```tsx
import { Skeleton } from "@/components/ui/skeleton";
```

Dans le rendu, juste avant `{rows.slice(0, PAGE_SIZE).map((a) => {`, ajouter :

```tsx
        {loading && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "4px 14px" }}>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <Skeleton className="size-10 shrink-0 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        )}
        {!loading &&
          rows.slice(0, PAGE_SIZE).map((a) => {
```

(la fermeture du `.map` existant ne change pas ; seul le `rows.map` devient
`!loading && rows.slice(0, PAGE_SIZE).map`, pour que le squelette et la liste
ne s'affichent jamais ensemble.)

L'état vide (`EmptyState` « Aucun athlète trouvé ») et le message « Saisis au
moins 2 lettres… » restent conditionnés par `!loading` implicitement, car
`rows` est vide et non encore recalculé tant que `loading` est vrai — vérifier
au Step 4 qu'aucun des deux ne s'affiche pendant le chargement (déjà couvert
par l'assertion `queryByText("Aucun athlète trouvé")` du test).

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx`
Expected: PASS (tout le fichier, y compris le nouveau test)

- [ ] **Step 5: Commit**

```bash
git add frontend/components/layout/AthletePicker.tsx frontend/components/layout/AthletePicker.test.tsx
git commit -m "fix(a11y): show a loading skeleton in the athlete picker

loading was already tracked but only used to suppress the empty
state — the results area stayed blank for the 250ms debounce plus
network time, with nothing telling the user a search was in flight.

Refs #484"
```

---

### Task 6: Frontend — `listbox` ARIA, navigation clavier, compte annoncé, « trop de résultats »

**Files:**
- Modify: `frontend/components/layout/AthletePicker.tsx`
- Modify: `frontend/components/layout/AthletePicker.test.tsx`

**Interfaces:**
- Consumes: `rows: AthleteSearchResult[]`, `PAGE_SIZE` (Task 3), `loading`
  (Task 5) — tous déjà en place.
- Produces: rien de nouveau consommé ailleurs — tâche terminale de la
  couture.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `AthletePicker.test.tsx` :

```tsx
describe("AthletePicker — listbox accessible (NAV-8, #484)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    searchAthletes.mockResolvedValue([
      { id: 1, nom: "GAUDIN", prenom: "Marie", gender: "", club: "TCN", participation_count: 3 },
      { id: 2, nom: "GAULT", prenom: "Eric", gender: "", club: "TCN", participation_count: 1 },
    ]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function ouvrirAvecResultats(user: ReturnType<typeof userEvent.setup>) {
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);
    const champ = screen.getByPlaceholderText("Rechercher un nom…");
    await user.type(champ, "gau");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    await screen.findByText("Marie GAUDIN");
    return champ;
  }

  it("expose un role=listbox avec des role=option", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await ouvrirAvecResultats(user);

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(2);
  });

  it("la flèche bas active la première option, puis la deuxième", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const champ = await ouvrirAvecResultats(user);

    await user.type(champ, "{ArrowDown}");
    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");

    await user.type(champ, "{ArrowDown}");
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    expect(champ).toHaveAttribute(
      "aria-activedescendant",
      screen.getAllByRole("option")[1].id,
    );
  });

  it("Entrée choisit l'option active", async () => {
    const onPick = vi.fn();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={onPick} />);
    const champ = screen.getByPlaceholderText("Rechercher un nom…");
    await user.type(champ, "gau");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    await screen.findByText("Marie GAUDIN");

    await user.type(champ, "{ArrowDown}{ArrowDown}{Enter}");

    expect(onPick).toHaveBeenCalledWith({ id: 2, prenom: "Eric", nom: "GAULT" });
  });

  it("annonce le nombre de résultats dans une région live", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await ouvrirAvecResultats(user);

    expect(screen.getByText("2 athlètes trouvés")).toHaveAttribute("aria-live", "polite");
  });

  it("affiche une précision quand il y a plus de résultats que la borne", async () => {
    searchAthletes.mockResolvedValue(
      Array.from({ length: 13 }, (_, i) => ({
        id: i,
        nom: `GAU${i}`,
        prenom: "A",
        gender: "",
        club: "TCN",
        participation_count: 1,
      })),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<AthletePicker onClose={vi.fn()} onPick={vi.fn()} />);
    await user.type(screen.getByPlaceholderText("Rechercher un nom…"), "gau");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });

    expect(await screen.findAllByRole("option")).toHaveLength(12);
    expect(screen.getByText(/précisez votre recherche/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx -t "listbox accessible"`
Expected: FAIL — pas de `role="listbox"`/`role="option"` aujourd'hui, pas de
navigation clavier, pas de région live, pas de message « trop de résultats ».

- [ ] **Step 3: Implémenter la `listbox` ARIA**

Dans `frontend/components/layout/AthletePicker.tsx`, ajouter un état pour
l'option active et un identifiant stable pour les options :

```tsx
  // -1 : aucune option active tant qu'aucune flèche n'a été pressée — la
  // première `ArrowDown` doit activer la **première** option, pas la deuxième.
  const [activeIndex, setActiveIndex] = useState(-1);
  const listboxId = useId();

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveIndex(-1);
  }, [rows]);

  const resultatsAffiches = rows.slice(0, PAGE_SIZE);
  const trapPlein = rows.length > PAGE_SIZE;

  function optionId(id: number) {
    return `${listboxId}-option-${id}`;
  }

  function choisir(a: AthleteSearchResult) {
    onPick({ id: a.id, prenom: a.prenom, nom: a.nom });
  }
```

(`useId` doit être ajouté à l'import React existant : `import { useEffect, useId, useState } from "react";`.)

Remplacer le bloc `<Input .../>` pour lui ajouter la sémantique `combobox` et
la navigation clavier :

```tsx
      <Input
        icon={<span>⌕</span>}
        value={query}
        autoFocus
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher un nom…"
        role="combobox"
        aria-expanded={resultatsAffiches.length > 0}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={
          resultatsAffiches[activeIndex] ? optionId(resultatsAffiches[activeIndex].id) : undefined
        }
        onKeyDown={(e) => {
          if (resultatsAffiches.length === 0) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIndex((i) => Math.min(i + 1, resultatsAffiches.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIndex((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            const actif = resultatsAffiches[activeIndex];
            if (actif) choisir(actif);
          }
        }}
      />
```

Remplacer le rendu des lignes (le bloc `!loading && rows.slice(0, PAGE_SIZE).map((a) => {...})`
ajouté en Task 5) par une vraie `listbox` :

```tsx
        {!loading && resultatsAffiches.length > 0 && (
          <div
            role="listbox"
            id={listboxId}
            aria-label="Athlètes trouvés"
            style={{ maxHeight: 6 * 62, overflowY: "auto" }}
          >
            {resultatsAffiches.map((a, i) => {
              const fullName = nomComplet(a);
              return (
                <div
                  key={a.id}
                  id={optionId(a.id)}
                  role="option"
                  aria-selected={i === activeIndex}
                  onClick={() => choisir(a)}
                  onMouseEnter={() => setActiveIndex(i)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    padding: "11px 14px",
                    borderRadius: 12,
                    cursor: "pointer",
                    background: i === activeIndex ? "var(--tcn-fill)" : "transparent",
                  }}
                >
                  <Avatar name={fullName} size={40} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, color: "var(--tcn-ink)", fontSize: 15 }}>
                      {fullName}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>
                      {a.club ?? "Sans club"} · {a.participation_count} épreuve
                      {a.participation_count > 1 ? "s" : ""}
                    </div>
                  </div>
                  <span style={{ color: "var(--tcn-text-disabled)", fontSize: 18 }}>→</span>
                </div>
              );
            })}
          </div>
        )}
        {!loading && trapPlein && (
          <div style={{ padding: "10px 14px", fontSize: 13, color: "var(--tcn-text-faint)" }}>
            Trop de résultats — précisez votre recherche.
          </div>
        )}
        <div aria-live="polite" className="sr-only">
          {loading
            ? "Recherche en cours"
            : query.trim().length >= 2
              ? `${resultatsAffiches.length} athlète${resultatsAffiches.length > 1 ? "s" : ""} trouvé${resultatsAffiches.length > 1 ? "s" : ""}`
              : ""}
        </div>
```

(`className="sr-only"` est déjà une classe Tailwind standard du projet, visible
dans `EmptyState`/composants existants — masque visuellement sans retirer du
DOM ni de l'arbre d'accessibilité.)

Retirer le `role="button"`/`onKeyDown` individuel de l'ancienne ligne (déjà
remplacé ci-dessus) et retirer les gestionnaires `onFocus`/`onBlur` de survol
au clavier devenus inutiles (`aria-selected`/`onMouseEnter` les remplacent).

L'état vide (`EmptyState`) doit maintenant se déclencher sur
`!loading && query.trim().length >= 2 && resultatsAffiches.length === 0` (au
lieu de `rows.length === 0`) — vérifier cette condition dans le JSX existant et
l'ajuster si elle référence encore `rows` directement.

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/layout/AthletePicker.test.tsx`
Expected: PASS (tout le fichier)

- [ ] **Step 5: Lancer tout Vitest et le typecheck**

Run: `cd frontend && npm test && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 6: Lint**

Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/components/layout/AthletePicker.tsx frontend/components/layout/AthletePicker.test.tsx
git commit -m "fix(a11y): make the athlete picker a real listbox

Replaces the div role=button rows (up to 12 tab stops) with
role=listbox/option, aria-activedescendant, arrow-key navigation and
Enter, a live-region result count, and a distinct 'too many results'
hint separate from the empty state — closes out NAV-8 (#484).

Refs #484"
```

---

## Self-Review (fait par l'auteur du plan)

**Couverture du design** :
- § 3.1/4.1 (route backend) → Tasks 1-2.
- § 3.2/4.3 (listbox à la main, pas de nouvelle primitive `ui/`) → Task 6,
  aucun fichier créé sous `components/ui/`.
- § 3.3/4.3 (piège de focus dans `Modal`) → Task 4.
- § 4.3 (squelette 3 lignes) → Task 5.
- § 4.3 (« trop de résultats » distinct de vide, hauteur bornée + scroll) →
  Task 6.
- § 4.4 (suppression de l'agrégation client, pas de repli) → Task 3, Step 5
  (le type `AthleteRow` et l'ancienne logique de tri/`slice` disparaissent,
  ne sont pas conservés en fallback).
- § 6 (plan de tests) → une tâche par bloc de tests listé dans le design.

**Cohérence des types** : `AthleteSearchResult` (Task 2 schema Python, Task 3
type TS) porte les mêmes champs des deux côtés
(`id, nom, prenom, gender, club, participation_count`) ; `PickedAthlete`
(`{id, prenom, nom}`, inchangé, défini en tête d'`AthletePicker.tsx`) reste ce
que `onPick`/`choisir` construisent — vérifié identique aux Tasks 3 et 6.
`PAGE_SIZE` introduit en Task 3, réutilisé sans redéfinition en Tasks 5 et 6.

**Aucun placeholder** : chaque step porte le code exact à écrire ; aucun
« TODO »/« gérer les cas limites » sans détail.
