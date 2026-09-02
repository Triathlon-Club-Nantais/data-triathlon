# Research: Écran de validation admin des déclarations de crédit d'athlète (#817)

## D1 — Combler l'absence de nom d'athlète par une relation, pas un endpoint neuf

**Décision** : ajouter `VolunteerAction.athlete` (relation SQLAlchemy vers
`Athlete`, aux côtés de `declared_by` déjà existante), une propriété Python
`athlete_nom`/`athlete_prenom` en lecture sur le modèle (jamais une colonne,
jamais une `hybrid_property` — rien ici n'a besoin d'être requêtable en SQL,
contrairement à `Course.is_reliable`), deux champs
`athlete_nom: str`/`athlete_prenom: str` dans `AdminVolunteerActionOut`, et
un `selectinload(VolunteerAction.athlete)` dans
`volunteer_action_repository.list_pending()`.

**Rationale** : `AdminVolunteerActionOut` n'expose que `athlete_id` — un
administrateur ne peut pas dire pour qui une déclaration a été soumise sans
consulter une autre page. Aucun endpoint de lookup en masse par ids
n'existe, et en créer un serait une indirection de plus pour un besoin qui
se résout par une jointure d'une ligne. `selectinload` évite le N+1 sur la
liste (un `SELECT` supplémentaire, pas un par ligne).

## D2 — Aucune migration

**Décision** : la relation ne crée aucune colonne — `athlete_id` existe
déjà comme FK sur `VolunteerAction`. Aucune révision Alembic nécessaire.

**Rationale** : une relation SQLAlchemy est une construction Python pure au
niveau du mapping ORM, elle ne change pas le schéma physique.

## D3 — Patron frontend : reprendre `AdminVolunteerDeclarationTable.tsx`

**Décision** : le nouveau composant `AdminVolunteerActionsTable.tsx` reprend
la structure du composant retiré par #816
(`git show 6454991d:frontend/components/benevolat/
AdminVolunteerDeclarationTable.tsx`) — `ui/table`, `ui/card`, `ui/skeleton`,
`ui/empty-state`, `messageDeRefus`, la même cascade d'états (chargement,
refus, vide, données).

**Rationale** : c'est le seul précédent direct dans ce dépôt pour un
tableau admin de déclarations de bénévolat — pas de raison d'inventer un
autre patron. Deux différences assumées avec ce précédent : pas de bascule
« consultation vs gestion » (`peutGerer`) — le pouvoir qui ouvre cet écran
(`athletes:volunteer_validate`) est déjà celui qui accepte/refuse, un seul
pouvoir pour tout l'écran, contrairement à `benevolat:read`/`_manage` qui en
distinguait deux ; et pas de `DangerConfirm` — accepter/refuser change un
statut, réversible par l'action inverse, ce n'est pas un geste destructif
au sens de `frontend/AGENTS.md` § Gestes destructifs (contrairement à la
suppression, #818).

## D4 — Nouvel id de navigation, pas de réutilisation

**Décision** : l'entrée de navigation prend un id distinct
(`a-benevolat-validation`), pas celui retiré par #816
(`a-benevolat`, doublon orphelin compris).

**Rationale** : réutiliser l'ancien id risquerait de faire réapparaître une
confusion entre deux fonctionnalités différentes (l'ancienne
auto-déclaration, celle-ci) si un historique de configuration ou un test
s'y référait encore par nom. Un id neuf pour une ressource neuve suit le
même principe que le reste du catalogue de navigation (chaque écran a son
id propre).
