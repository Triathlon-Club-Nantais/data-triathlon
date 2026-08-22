# Design — NAV-8 : la palette de recherche d'athlète (#484)

Classification brainstorming : **architectural** (deux couches touchées — front
et back —, et le contrat public `GET /athletes` est concerné par la question
posée dans l'issue). Voie Superpowers, phase design uniquement ; l'exécution
suit `writing-plans` puis l'exécuteur choisi par l'utilisateur.

## 1. Contexte

`NAV-8` du § 5 de `docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`
liste cinq défauts de la palette `⌘K` (`AthletePicker.tsx`, ouverte depuis
`AppNav.tsx`, rendue dans `Modal` de `components/tcn/`) :

1. Zone de résultats entièrement vide pendant les 250 ms de debounce + réseau
   — `loading` est calculé mais ne sert qu'à masquer l'état vide.
2. Résultats en `div role="button" tabIndex={0}` : pas de `listbox`/`option`,
   aucune navigation aux flèches, jusqu'à 12 tabulations.
3. `Modal` ne piège ni ne restaure le focus à la fermeture.
4. La liste agrège côté client les 100 premières **participations**
   correspondant au nom (`apiClient.listParticipations({name:q,
   page_size:100})`) et n'en garde que 12 athlètes : un athlète peu couru sur
   un patronyme fréquent peut être absent de l'agrégat alors qu'il existe.
5. Le tri retenu est par nombre de courses, pas par qualité de correspondance
   — un patronyme approché mais peu couru passe devant une correspondance
   exacte peu courue.

Deux consommateurs de `Modal` existent dans le front : `AthletePicker`
(`components/layout/`) et `CourseSourcesPanel` (`components/courses/`). Le
correctif de piège de focus (point 3) est posé dans `Modal.tsx` lui-même
(`components/tcn/`) et profite donc aux deux, sans changement de comportement
visible pour `CourseSourcesPanel`.

`GET /athletes` existe déjà côté backend (`app/api/v1/athletes.py`,
`athlete_repository.search`) mais **n'a aucun consommateur front actuel** —
`AthletePicker` interroge `/participations`, pas `/athletes`. C'est la racine
du défaut 4 : les 100 lignes plafonnées sont des participations, pas des
athlètes, et l'agrégation qui en découle est en Python, côté client.

## 2. Ce qui ne bouge pas

Contraintes non négociables de #325, reconduites ici :

- Identité arbitrée : aucun token `--tcn-*`, aucune police, aucun dégradé ne
  change.
- Frontière `components/tcn/` vs `components/ui/`
  (`frontend/AGENTS.md` § « Deux bibliothèques, une frontière ») : pas
  rejugée, seulement appliquée (§ 3.2 explique le choix retenu pour cette
  palette précise).
- Contrat public `/api/v1` : rien d'existant n'est retiré ni modifié en place ;
  voir § 3.1 pour l'arbitrage précis.
- Le stock `localStorage` de l'athlète retenu, `useIsSelectedAthlete` et
  `ATHLETE_CHANGED_EVENT` (#467) restent inchangés — ce lot touche la
  *recherche*, pas la sélection ni la mémorisation.

## 3. Décisions d'architecture

### 3.1 Backend : un nouvel endpoint `GET /athletes/search`, pas une modification de `GET /athletes`

**Décision tranchée seule** (pas d'arbitrage produit — c'est un choix
d'ingénierie sur la forme du contrat, documenté ici plutôt que remonté) :
ajouter une route neuve, **`GET /athletes/search`**, plutôt que de modifier le
comportement de `GET /athletes`.

Raisons :
- `GET /athletes` a un contrat déjà publié (`response_model=list[AthleteBrief]`,
  ordre `nom, prenom`) même s'il n'a aujourd'hui aucun appelant connu dans ce
  dépôt — un appelant externe est plausible (script, futur client mobile) et
  le Principe IV interdit de lui changer silencieusement son ordre de tri ou
  la forme de sa réponse.
- Le besoin de la palette est net et distinct : classement par pertinence,
  compte de participations par athlète, borne stricte (12) — trois choses que
  `GET /athletes` ne fait pas et n'a pas de raison de faire pour ses usages
  actuels (listes paginées, `scope=club`).
- Une route neuve peut évoluer et se retirer librement (aucun contrat pris),
  ce qui respecte mieux « pas de compatibilité ascendante à préserver, mais
  l'API publiée ne se casse pas silencieusement » que d'ajouter un paramètre
  optionnel qui changerait le tri implicite d'une route existante.

Forme retenue :

```
GET /athletes/search?q=<terme>&scope=<club|vide>&limit=<1..50, défaut 12>
→ 200 list[AthleteSearchResult]
```

- `q` : requis, `min_length=2` — même seuil que le front applique déjà avant
  d'appeler l'API ; le backend le refait valoir (422 sinon) pour ne pas
  dépendre d'un appelant qui l'oublierait.
- `scope=club` : même sémantique que partout ailleurs (`is_club_scope`),
  optionnel — la palette actuelle ne filtre pas par club, ce comportement est
  préservé par défaut.
- `limit` : la palette demandera `limit=13` (12 + 1) pour distinguer « 12
  résultats pile » de « plus de 12, précise ta recherche » sans requête
  supplémentaire (§ 4.3).
- `AthleteSearchResult(AthleteBrief)` ajoute `participation_count: int` — même
  patron que `AthleteSeasonActivity`, qui ajoute déjà un compte à un sous-jeu
  de champs d'athlète. Pas de `birth_date` : cette route reste publique
  (derrière `require_site_access`, comme `/athletes` aujourd'hui), et
  `athlete_repository.search_admin` documente déjà pourquoi la date de
  naissance reste réservée à `athletes:read`.
- Déclarée **avant** `GET /athletes/{athlete_id}` dans le routeur, sur le
  même besoin que `/athletes/season-activity` (commentaire déjà en place à
  `athletes.py:29-30`) : sinon FastAPI matcherait `search` comme un
  `athlete_id` invalide (422) au lieu de résoudre la route.
- Garde d'accès : héritée automatiquement de `require_site_access`, posée par
  préfixe de routeur dans `v1/router.py` — `athletes` n'est pas dans
  `_EXEMPTES_DE_LA_GARDE_SITE`, donc la nouvelle route hérite de la même garde
  que `/athletes` et `/participations` aujourd'hui. Rien à ajouter.
- Pas de plafond de débit dédié : ce n'est pas une écriture publique ni une
  route d'authentification (cf. la liste fermée de `deps.py`), et elle est
  déjà derrière le mot de passe de site — cohérent avec `/athletes` qui n'en a
  pas non plus.

**Repository** — nouvelle fonction `athlete_repository.search_by_relevance`,
sœur de `search_admin` (même jointure `outerjoin(Participation)` +
`group_by(Athlete.id)` pour le compte), qui ajoute un classement :

```python
def search_by_relevance(
    db: Session, *, term: str, club_only: bool = False, limit: int = 12
) -> list[tuple[Athlete, int]]:
    compte = func.count(Participation.id)
    rang = _relevance_rank(term)          # 0 préfixe exact, 1 début de mot, 2 sous-chaîne
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

`_relevance_rank(term)` calcule, pour `nom` et pour `prenom`, un score sur le
terme **entier** (déaccentué, en minuscule — même traitement que
`name_filter`, dont l'échappement `LIKE` est extrait en un petit helper
partagé plutôt que dupliqué) :

- **0 — préfixe exact** : le champ commence par le terme
  (`unaccent(lower(champ)) LIKE 'terme%'`).
- **1 — début de mot** : le terme suit un séparateur interne — espace, trait
  d'union, apostrophe (`LIKE '% terme%'`, `LIKE '%-terme%'`, `LIKE '%''terme%'`)
  — et n'est pas déjà en position 0.
- **2 — sous-chaîne** : matché par `name_filter` sans être dans les deux
  buckets ci-dessus (le cas déjà couvert aujourd'hui, sans distinction).

Le rang retenu par athlète est le **meilleur** (le plus petit) des deux rangs
`nom`/`prenom` — `least(rang_nom, rang_prenom)` en SQL, ou un `case()` imbriqué
équivalent selon ce que SQLAlchemy expose proprement sur les deux moteurs
(SQLite/PostgreSQL) ; à vérifier au moment d'écrire le test, pas de blocage de
principe.

**Portée volontairement limitée** : le classement travaille sur le terme
**entier**, pas mot à mot comme `name_filter`. Un « Jean Dupont » qui ne
préfixe ni ne commence un mot d'aucun des deux champs retombe en bucket 2
(sous-chaîne) — jamais pire qu'aujourd'hui, jamais faux, seulement moins fin
qu'un vrai classement multi-mots. La preuve de terrain de l'audit porte sur
une requête à un seul mot (« Herr ») ; complexifier pour un cas non mesuré
serait de la spéculation (Principe « implémentation la plus simple »).

**Départage par volume, à l'intérieur d'un même bucket** — précision qui lève
une ambiguïté de lecture de l'audit : « Herr » matche « HERRMANN » et
« Herry » tous deux en bucket 0 (préfixe exact des deux noms) ; entre les
deux, le nombre de courses reste le départage, conformément à « classer par
correspondance **avant** le volume » — le volume n'est écarté qu'entre buckets
différents, jamais à l'intérieur d'un même bucket. Ce que l'audit démontre et
que ce classement corrige réellement, c'est que CHERRUEAU / CHERRIER /
CHERRUAULT (bucket 2, sous-chaîne au milieu du nom) ne doivent plus jamais
dépasser un préfixe exact ou un début de mot, quel que soit leur volume.

### 3.2 Frontend : pas de nouvelle primitive `ui/`, un `listbox` ARIA écrit à la main dans `AthletePicker.tsx`

`@base-ui/react` (déjà une dépendance) expose un composant `Combobox` complet
(`Root/Input/List/Item/Empty/Status`, vérifié dans le paquet installé). Il a
été envisagé et écarté pour ce lot :

- Son modèle est celui d'un champ avec une **liste flottante ancrée**
  (`Positioner`/`Popup`/`Portal`, pensé pour un autocomplete sous un input) ;
  notre palette a la forme inverse — la liste vit **dans le corps de la
  `Modal`**, jamais flottante, jamais positionnée par rapport à l'input. Le
  plier à cet usage demande de contourner une bonne partie de son modèle de
  positionnement pour ne garder que la sémantique ARIA — un gain net
  incertain pour un seul site d'appel.
- La frontière de `frontend/AGENTS.md` réserve `ui/` aux « primitives
  accessibles sans équivalent TCN » — un principe qui vaut pour une
  abstraction **réutilisée**, pas pour justifier d'en introduire une nouvelle
  quand un seul écran en a besoin (YAGNI, Principe « pas d'abstraction
  spéculative »). `AthletePicker` est aujourd'hui le seul endroit du site à
  avoir la forme d'une palette de commande.
- La surface ARIA demandée par l'« Attendu » de l'issue (`role="listbox"`,
  `aria-activedescendant`, flèches, `Entrée`, compte annoncé) est un patron
  WAI-ARIA Combobox/Listbox standard, borné à quelques dizaines de lignes,
  déjà dans l'esprit du fichier actuel qui gère lui-même son `role="button"`
  et son `onKeyDown`.

**Décision** : écrire le `listbox` à la main, directement dans
`AthletePicker.tsx`, avec les tokens `--tcn-*` existants pour le style —
aucun nouveau fichier dans `components/ui/` ni `components/tcn/`. Si un
second besoin de palette de commande apparaît ailleurs dans le site,
l'extraction vers `ui/` se rejugera à ce moment, avec deux sites d'appel réels
pour la motiver.

### 3.3 Piège de focus : dans `Modal.tsx` (`components/tcn/`), générique

Le point 3 se corrige dans `Modal`, pas dans `AthletePicker` : c'est le seul
endroit qui connaît l'ouverture/fermeture pour les deux consommateurs
(`AthletePicker`, `CourseSourcesPanel`). À l'ouverture (montage avec
`open !== false`), `Modal` capture `document.activeElement` s'il s'agit d'un
`HTMLElement` ; à la fermeture (démontage, ou passage à `open=false`), il lui
rend le focus s'il est toujours attaché au document. Le piège de focus
(Tab/Shift+Tab ne sortent jamais de la boîte de dialogue) s'implémente par une
recherche des éléments focalisables du conteneur `role="dialog"` à chaque
`keydown` de Tab — pas de nouvelle dépendance, patron déjà utilisé pour
`Escape` dans le même fichier (`useEffect` + `addEventListener("keydown", …)`).

## 4. Design détaillé

### 4.1 Backend — schéma et route

`app/schemas/athlete.py` :

```python
class AthleteSearchResult(AthleteBrief):
    participation_count: int
```

`app/api/v1/athletes.py`, déclarée avant `/athletes/{athlete_id}` :

```python
@router.get("/athletes/search", response_model=list[AthleteSearchResult])
def search_athletes(
    q: str = Query(..., min_length=2),
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    lignes = athlete_repository.search_by_relevance(
        db, term=q, club_only=is_club_scope(scope), limit=limit
    )
    return [
        AthleteSearchResult(**AthleteBrief.model_validate(a).model_dump(), participation_count=n)
        for a, n in lignes
    ]
```

### 4.2 Frontend — `apiClient`

Nouvelle méthode, sur le patron de `searchAthletesAdmin`/`searchAthletesBenevole` :

```ts
searchAthletes: (q: string, limit = 13) =>
  request<AthleteSearchResult[]>(`/athletes/search${toQuery({ q, limit })}`),
```

`AthleteRow` devient `AthleteSearchResult` (le type vient du backend via
`lib/types.ts`), avec `participation_count` renommé `count` uniquement en
affichage si besoin — pas de renommage côté type pour rester au plus près du
contrat.

### 4.3 Frontend — `AthletePicker.tsx`, état et rendu

États dérivés d'une seule machine simple (pas de librairie d'état neuve) :

| État | Condition | Rendu |
| --- | --- | --- |
| `hint` | `query.trim().length < 2` | message actuel « Saisis au moins 2 lettres… » (inchangé) |
| `loading` | requête en vol | squelette de **trois lignes** (`Skeleton` de `components/ui/skeleton.tsx`, même composant que les `loading.tsx` de routes récentes) — remplace l'actuel vide silencieux |
| `empty` | requête terminée, 0 résultat | `EmptyState` actuel, inchangé |
| `too-many` | requête terminée, `results.length > 12` (donc `limit=13` a rendu son 13ᵉ) | les 12 premiers résultats **+** une ligne de précision « Trop de résultats — précise ta recherche », sous la liste, jamais à la place |
| `results` | requête terminée, `1..12` résultats | la liste en `listbox` |

Liste en `listbox` :

```tsx
<input
  role="combobox"
  aria-expanded={rows.length > 0}
  aria-controls={listboxId}
  aria-activedescendant={activeId}
  aria-autocomplete="list"
  ...
/>
<div role="listbox" id={listboxId} aria-label="Athlètes trouvés"
     style={{ maxHeight: 6 * ROW_HEIGHT, overflowY: "auto" }}>
  {rows.map((a, i) => (
    <div role="option" id={optionId(a.id)} aria-selected={i === activeIndex} ... />
  ))}
</div>
<div aria-live="polite" className="sr-only">
  {loading ? "Recherche en cours" : `${rows.length} athlète${rows.length > 1 ? "s" : ""} trouvé${rows.length > 1 ? "s" : ""}`}
</div>
```

- Flèches haut/bas déplacent `activeIndex` (bornées, pas de wrap — cohérent
  avec la loi de Jakob citée par l'audit : c'est le comportement standard
  d'un `⌘K`) ; `Entrée` choisit l'option active ; le clic/`Entrée` existants
  sont conservés.
- Hauteur bornée à 6 lignes visibles avec défilement — le pied de modale ne
  coupe plus la liste en cours de ligne (dernier point du défaut 5).
- `aria-live="polite"` annonce le compte ou l'état de recherche — répond à
  « distinguer aucun résultat de trop de résultats » et au A11Y-5 déjà relevé
  ailleurs dans l'audit (le patron `role="status"` existe déjà dans le code
  base, réutilisé ici).

### 4.4 Suppression, pas de compatibilité

`apiClient.listParticipations` reste utilisé ailleurs (inchangé) ; seul son
usage dans `AthletePicker` disparaît, avec toute la logique d'agrégation
(`Map<number, AthleteRow>`, tri par `count`, `slice(0, 12)`) — supprimée, pas
gardée en repli. Conforme au principe « pas de compatibilité ascendante à
préserver » du projet.

## 5. Erreurs et cas limites

- Échec réseau : `catch` existant conservé, retombe sur `rows = []`, donc sur
  l'état `empty` — un échec réseau silencieux qui affiche « Aucun athlète
  trouvé » est trompeur, mais c'est un défaut déjà présent aujourd'hui et
  **hors périmètre strict de NAV-8** (l'audit ne le relève pas). Noté ici
  pour mémoire, à ne pas corriger dans ce lot pour ne pas élargir la couture
  (un futur `ETAT-*` le couvrira si mesuré).
- Course en vol annulée (`cancelled` flag) : comportement conservé à
  l'identique, juste rebranché sur le nouvel appel.
- `q` de moins de 2 caractères après un `trim()` avec espaces en tête/fin :
  comportement actuel conservé (le front ne requête pas, donc le 422 backend
  sur `min_length=2` n'est jamais atteint par ce chemin).
- Terme contenant des jokers `LIKE` (`%`, `_`) : déjà échappé par
  `name_filter` ; le rang de pertinence réutilise le même échappement.

## 6. Tests

**Backend (pytest, TDD)** :
- `test_repositories/test_athlete_repository.py` : `search_by_relevance` —
  préfixe exact devant début de mot devant sous-chaîne ; volume comme
  départage intra-bucket ; `club_only` ; `limit` respecté ; terme de 1
  caractère laissé à l'appelant (la fonction ne valide pas `min_length`, la
  route le fait).
- `test_api/test_athletes.py` : `GET /athletes/search` — 422 sous 2
  caractères ; forme `AthleteSearchResult` (présence de
  `participation_count`, absence de `birth_date`) ; **test de précédence de
  route** sur le patron de `/athletes/season-activity` (`search` ne doit pas
  être capturée par `/athletes/{athlete_id}`) ; garde `require_site_access`
  héritée (test dans la suite existante de `test_site_access_gate.py`, à
  étendre plutôt qu'à dupliquer).

**Frontend (vitest + RTL, TDD)** :
- `AthletePicker.test.tsx`, réécrit pour mocker `apiClient.searchAthletes` au
  lieu de `listParticipations` :
  - squelette visible pendant le `loading` (assertion sur le rôle/texte du
    squelette, pas sur un délai arbitraire) ;
  - navigation clavier : flèche bas sélectionne la première option,
    `aria-activedescendant` suit, `Entrée` appelle `onPick` avec l'athlète
    actif ;
  - compte annoncé dans la région `aria-live` ;
  - état « trop de résultats » distinct de l'état vide (13 résultats mockés
    → 12 rendus + le message de précision) ;
  - le test ETAT-3 existant (« aucun athlète trouvé ») continue de passer,
    adapté au nouveau mock.
- `Modal.test.tsx` (nouveau fichier, ou section ajoutée à un test existant de
  `CourseSourcesPanel`/`AppNav`) : à l'ouverture, le focus est piégé (Tab
  depuis le dernier élément focalisable revient au premier) ; à la fermeture,
  le focus revient à l'élément qui a ouvert la modale.

## 7. Hors périmètre (rappel, cohérent avec l'issue)

- Le dispositif « athlète retenu » (§ 10 de l'audit, `PROF-7`/`NAV-9`/`NAV-10`/
  `PROF-8`) : ce lot ne fait que réparer la porte d'entrée, il ne construit
  aucun des quatre usages listés.
- L'échec réseau silencieux de la palette (§ 5, note ci-dessus).
- Toute modification de `GET /athletes` existant.
