# Data Model: Re-scrape à la demande d'une course depuis le back-office

**Aucune migration.** Le modèle normalisé (`Course`, `Participation`,
`Athlete`, `PendingProvider`) est inchangé — cette feature ajoute un
déclencheur sur des écritures que le code sait déjà faire (import upsert,
purge d'orphelins), pas un nouveau champ ni une nouvelle table.

## Entités existantes touchées

### Course

Cible du re-scrape, désignée par `course_id` dans le chemin de la route. Seule
sa **source active** (`course.source_url`, via `course_sources`) est
réinterrogée — pas les sources passives. Les champs `name`, `event_date`,
`event_type`, `is_relay` **ne sont jamais réécrits** par un re-scrape — c'est
l'identité de la course, et `_require_same_event` (FR-009) refuse justement
tout scrape dont l'identité diverge de celle stockée avant d'écrire quoi que
ce soit. FR-004 (« mettre à jour les métadonnées ») a été **retirée** en revue
de code : incompatible par construction avec FR-009, elle décrivait une
capacité qui existe déjà ailleurs, sous un geste dédié
(`PATCH /admin/courses/{id}`, `courses:write`, #117).

### Participation

Mise à jour ou créée par dossard (`bib_number`), jamais dupliquée (FR-005) —
patron `_Persister.add`, identique à l'import public. Contrairement à la
bascule de source (#285), **aucune suppression préalable** : c'est l'upsert
existant qui porte la garantie de non-duplication, via la contrainte
`uq_participation_bib`.

### Athlete

Peut devenir orpheline d'une course si la réconciliation d'identité du
re-scrape la rattache ailleurs (FR-006). Candidats relevés **avant**
l'écriture (`athlete_repository.only_on_course(db, course_id)`), purge
tranchée **après** (`athlete_repository.delete_orphans_among`) — même ordre
que #117/#285, pour la même raison : après écriture, les candidats orphelins
ne se distingueraient plus des coureurs republiés par le chronométreur.

## État en mémoire (hors persistance)

### Verrou de concurrence par course (R5)

Pas une entité de données — un état **process**, non persisté :
`{course_id: bool}` protégé par un verrou, vivant le temps du process du
service web. Un redémarrage du service le réinitialise silencieusement (aucun
re-scrape ne peut être « bloqué » après coup) : propriété voulue, pas un
oubli.

## Contrat de progression SSE (transitoire, non persisté)

Les événements émis par `iter_rescrape_course` ne sont **pas stockés** — ils
transitent du générateur vers la réponse HTTP `text/event-stream`, lus une
fois par le navigateur qui a déclenché le re-scrape. Détail des phases :
[contracts/admin-rescrape-sse.md](./contracts/admin-rescrape-sse.md).
