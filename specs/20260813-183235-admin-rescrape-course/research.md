# Research: Re-scrape à la demande d'une course depuis le back-office

Toutes les inconnues techniques de la spec ont été résolues par lecture directe
du code existant (`import_service.py`, `admin_actions.py`,
`admin_course_sources.py`, `scrape.py`) — aucune n'a justifié un
`[NEEDS CLARIFICATION]` en spec. Ce document consigne les décisions et leurs
alternatives rejetées.

## R1 — Pas de mécanisme de job id / polling

**Decision**: `POST /admin/courses/{course_id}/rescrape` répond directement en
`text/event-stream` (comme `POST /scrape/event/stream`), sans identifiant de
job ni endpoint de polling séparé.

**Rationale**: le libellé de l'issue #118 (« retourne un identifiant de job »)
a été écrit avant que #275/#285 tranchent le mécanisme de progression. Le seul
mécanisme SSE existant dans le code est le patron
`import_service.iter_import_event` + `StreamingResponse`, consommé par une
connexion fetch tenue ouverte côté front (`lib/api/sse.ts`,
`hooks/useImportStream.ts`) — aucun job store n'existe, et
`backend/app/api/AGENTS.md` documente explicitement que #275 a voulu **un seul**
mécanisme de progression pour la bascule de source et le re-scrape à la
demande, pas deux. Introduire un job id serait une troisième mécanique pour un
seul consommateur (le navigateur qui vient de cliquer), ce que le principe VI
(YAGNI) écarte.

**Alternatives considered**: réutiliser le mécanisme `batch_runs.py` (GitHub
Actions + polling) — écarté, il cible un tout autre besoin (batches longs,
plusieurs heures, décorrélés du service web) et n'a pas de sortie SSE.

## R2 — Cache TTL désarmé par heat : étendre `_scrape_all_streaming`

**Decision**: ajouter `use_cache_probe: bool = True` à
`import_service._scrape_all_streaming` et `iter_import_event`, sur le même
principe que le paramètre déjà présent sur `_scrape_all` (utilisé par
`scrape_for_replacement` pour #285). L'appel admin passe `False`.

**Rationale**: `force=True` sur `iter_import_event` ne court-circuite que le
cache **global** (`_cached_result`) ; `_scrape_all_streaming` construit
toujours un `cache_probe` et le passe au dispatcher fan-out. Sur une épreuve
Klikego/RaceResult récemment scrapée — le cas exact d'un re-scrape demandé —
chaque heat serait jugé frais et sauté, laissant le classement inchangé malgré
la demande explicite. `backend/app/api/AGENTS.md` documente déjà ce piège pour
#285 (« le cache TTL est neutralisé des deux côtés ») ; #118 a le même besoin,
côté streamé cette fois.

**Alternatives considered**: dupliquer `_scrape_all_streaming` dans
`rescrape_service.py` avec le cache désarmé en dur — rejeté, duplique ~70
lignes pour une différence d'un paramètre, et diverge du principe VI.

## R3 — Upsert, pas remplacement total : nouveau générateur dans `admin_actions.py`

**Decision**: `admin_actions.iter_rescrape_course(db, *, course_id, user_id,
settings) -> Iterator[dict]`, sibling de `switch_course_source` mais
streaming, ciblant l'URL de la source **active** de la course (pas une source
différente), et persistant via le patron `_Persister` / upsert par dossard
(comme l'import public) — jamais suppression-puis-réimport.

**Rationale**: l'issue #118 demande explicitement « participations mises à
jour selon la règle habituelle (upsert par bib_number) », alors que #285 (la
bascule) **détruit puis réimporte** intégralement (décision D2 de #275) parce
qu'elle change de chronométreur — deux sémantiques différentes pour deux
gestes différents, documentées comme telles dans `admin_actions.py`. Réutiliser
le chemin de #285 tel quel appliquerait la mauvaise règle de persistance.

En revanche, les **gardes** de #285 s'appliquent à l'identique et sont
directement réutilisées : `_require_same_event` (refuse zéro résultat ou
épreuve divergente — FR-009), et la purge d'orphelins
`athlete_repository.only_on_course` (candidats **avant**) +
`delete_orphans_among` (purge **après**) — même primitive que #117/#285, pas
une redéfinition.

**Alternatives considered**: appeler `iter_import_event` tel quel sur l'URL de
la source active — rejeté, son chemin ordinaire ne referme aucune garde
d'identité (un zéro-résultat y est un succès à compteur nul, et une identité
divergente y créerait silencieusement une **nouvelle** `Course` plutôt que de
refuser) : correct pour un import libre, faux pour un geste ciblé sur un
`course_id` précis.

## R4 — Emplacement UI : la page publique `courses/[id]`, pas une page admin dédiée

**Decision**: le bouton « Re-scraper » et sa barre de progression rejoignent
`components/courses/CourseSourcesPanel.tsx`, rendu sur `app/courses/[id]/page.tsx`
— pas une nouvelle route `/admin/courses/{id}`.

**Rationale**: cette route n'existe pas dans le code (`app/admin/courses/page.tsx`
est une liste, sans détail par id), et le geste voisin — la bascule de source
(#285) — est déjà rendu sur la page publique de la course, gardé côté client
par `session.permissions.includes("courses:sources")` exactement comme
souhaité ici (FR-010). `frontend/AGENTS.md` confirme le patron : la lecture
des sources est publique (D4 de #275), seule l'action de bascule exige le
pouvoir. Créer une page admin dédiée dupliquerait l'affichage des sources déjà
présent, pour un gain nul.

**Alternatives considered**: nouvelle route `/admin/courses/[id]/page.tsx` —
rejetée, contredit le patron déjà posé par #284/#285 et le principe VI.

## R5 — Concurrence : verrou en mémoire, process unique

**Decision**: un verrou en mémoire (ex. `dict[int, bool]` protégé par un
`threading.Lock`), local au module `admin_actions.py`, clé = `course_id`.
Acquis à l'entrée du générateur, relâché en `finally`.

**Rationale**: le service web tourne en **un seul process** (offre gratuite —
documenté dans le docstring de `batch_runs.py`), donc un verrou en mémoire
process suffit à empêcher deux re-scrapes concurrents sur la même course
(FR-007/SC-005) sans introduire de dépendance externe (Redis, verrou DB).
`ponytail:` verrou process unique — si le service passe un jour multi-instance,
migrer vers un verrou DB (`SELECT … FOR UPDATE` sur la ligne `Course`, ou une
colonne `rescrape_lock_at`).

**Alternatives considered**: verrou en base (colonne ou table dédiée) — rejeté
pour l'instant, sur-dimensionné tant que le service reste single-process ;
compter sur `ensure_idle`-like polling de la plateforme (patron `batch_runs.py`)
— non applicable, ce geste ne passe pas par GitHub Actions.

## R6 — Permission : `courses:sources`, pas un nouveau pouvoir

**Decision**: `Depends(require_permission(P.COURSES_SOURCES))`, identique à la
bascule de source.

**Rationale**: `backend/app/api/AGENTS.md` établit déjà que #275 traite la
bascule et le re-scrape à la demande comme deux facettes d'un même mécanisme
d'administration des sources d'une épreuve. `courses:write` est explicitement
borné aux quatre champs d'identité (nom, date, type, relais) et ne convient
pas à un geste qui réécrit des résultats. Ajouter un pouvoir dédié
fragmenterait sans bénéfice un catalogue déjà cohérent.
