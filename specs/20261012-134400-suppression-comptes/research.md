# Research: Suppression des comptes

Décisions de conception, mesurées sur le code au 2026-10-12. Les décisions du mainteneur sont dans les Clarifications de la spec.

## D1. Inventaire des références vers `users.id`

**Décision**: lire l'inventaire dans `Base.metadata` (toute FK dont la cible est `users.id`), en excluant les quatre tables possédées par le compte (`identities`, `user_sessions`, `user_roles`, `user_groups`, emportées par la cascade ORM de `User`). Une colonne `nullable=False` bloque la suppression si une ligne la cite ; une colonne nullable est mise à `NULL`.

Inventaire mesuré (`grep 'users.id' app/models/`) :

| Obligatoire (bloque) | Facultative (mise à vide) |
|---|---|
| `admin_action_log.user_id` | `volunteer_actions.declared_by_user_id` |
| `season_validations.validated_by_user_id` | `athlete_oppositions.applied_by_user_id` |
| `ignored_course_duplicates.ignored_by_user_id` | `ignored_athlete_pairs.ignored_by_user_id` |
| `ignored_identity_cases.ignored_by_user_id` | `athlete_known_clubs.created_by_user_id` |
| `benevole_access_config.updated_by_user_id` | `site_access_config.updated_by_user_id` |
| | `allowed_emails.created_by_user_id`, `club_aliases`, `counter_scope_entries`, `course_sources`, `personal_profiles.created_by_user_id`, `profile_log_entries`, `user_feedback.user_id` |

**Rationale**: les FK n'ont pas d'`ondelete` et la contrainte n'est active qu'en PostgreSQL : une colonne oubliée dans une liste tenue à la main ne se verrait qu'en production, par une `IntegrityError`. La lecture du schéma couvre aussi la FK ajoutée demain. Un test fige l'inventaire obligatoire mesuré ci-dessus pour qu'un changement de nullabilité se voie en revue.

**Alternatives**: liste explicite dans le repository (rejetée, voir ci-dessus) ; `ondelete="SET NULL"` en base (rejeté : migration de dix-sept contraintes, inerte en SQLite où tournent dev et tests).

## D2. Auteur de la ligne de journal `account.delete`

**Décision**: le compte système (`SYSTEM_USER_EMAIL`, résolu par `benevole_access.system_user_id`), pour les deux origines. Payload `{"origin": "request" | "inactivity", "entra_oids": [...]}`, `entity_type="user"`, `entity_id` = l'identifiant supprimé. Le journal affiche « Système » pour ce geste (le nom du compte système, « Bénévoles (accès partagé) », laisserait croire à un geste bénévole).

**Rationale**: `admin_action_log.user_id` est obligatoire et porte une FK ; le compte supprimé ne peut pas en être l'auteur, et la purge n'a pas d'acteur. `audit.record` avec `actor_id=None` n'écrirait rien, alors que FR-009 exige la trace. Le compte système est semé par migration dans tous les environnements et n'est jamais supprimé (FR-006).

**Alternatives**: rendre `user_id` nullable (rejeté : change l'invariant du journal) ; ne pas tracer la purge (contraire à FR-009).

## D3. Dernier administrateur

**Décision**: la suppression s'exécute dans `authorization.administrateurs_preserves(db)` (toutes organisations), qui lève `LastAdministratorError` (409). Pour la purge, un compte avec rôle n'est jamais candidat, la garde est donc sans objet ; elle reste sur le chemin commun par sécurité.

## D4. Tenue de `last_seen_at`

**Décision**: `session.open_with_token` pose `user.last_seen_at = utcnow()` (même transaction que l'ouverture, commitée par le retour de parcours). `session.resolve`, si `last_seen_at.date() < utcnow().date()`, appelle `user_repository.touch_last_seen(db, user_id, now)`, un `UPDATE users SET last_seen_at = :now WHERE id = :id AND last_seen_at < :debut_du_jour`, exécuté et commité par une session à part liée au même moteur (révisé en revue de PR #1357 : un `db.commit()` sur la session de la requête commitait aussi ce qu'elle portait).

**Rationale**: `get_db` ne commite jamais ; une écriture non commitée serait perdue sur toute requête de lecture. La session à part laisse la transaction de la requête intacte ; l'objet de la requête est aligné par `set_committed_value`. La condition dans le `WHERE` rend deux requêtes concurrentes inoffensives (une seule écrit). Coût : une écriture par compte et par jour (SC-004).

**Alternatives**: session SQLAlchemy séparée (plus de code, une connexion de plus) ; mise à jour à chaque requête (contraire à SC-004).

## D5. Migration

**Décision**: ajouter la colonne nullable, `UPDATE users SET last_seen_at = COALESCE((SELECT MAX(created_at) FROM user_sessions WHERE user_id = users.id), created_at, CURRENT_TIMESTAMP)` (la dernière ouverture de session est la meilleure activité connue), puis la rendre `NOT NULL` dans un `batch_alter_table` (SQLite). Le modèle porte `default=utcnow`.

## D6. Route de suppression volontaire

**Décision**: `DELETE /api/v1/auth/me`, dépendance `current_user` (401 anonyme), 204 avec les mêmes effacements de cookies que `POST /auth/logout` (session, `tcn_logged_in`, cookie bénévoles) et les en-têtes `no-store`. Protection CSRF : celle de `logout`, `SameSite=Lax` plus `core/origin_guard` qui refuse toute écriture `DELETE` same-site ou cross-site. Pas de limiteur de débit : `logout` n'en a pas, et la route n'agit que sur le compte de la session.

## D7. Purge par inactivité

**Décision**: `accounts.purge_inactive(db, now, dry_run)` liste les candidats (`user_repository.list_inactive_without_role(db, cutoff)` : `last_seen_at < accounts.inactivity_cutoff(now)`, même date du calendrier 5 ans plus tôt, un 29 février devenant le 28 (révisé en revue : 5 × 365 jours retranchait un ou deux jours bissextiles), aucun `user_roles`, adresse différente de `SYSTEM_USER_EMAIL`), classe chacun en supprimable ou sauté (référence obligatoire), supprime les premiers hors passe à blanc. Appelée par `retention_service.purge_expired` **après** la purge du journal, pour que les lignes de plus de 12 mois ne bloquent plus. En passe à blanc, le journal n'est pas purgé : un compte cité seulement par des lignes de plus de 12 mois y est compté « sauté » alors que la passe réelle le supprimerait. Écart accepté et documenté.

## D8. Interface

**Décision**: entrée « Supprimer mon compte » dans le menu (déroulant et tiroir mobile), qui ouvre un `Dialog` shadcn déjà présent (`components/ui/dialog.tsx`) : titre, ce qui est effacé (compte, connexions, rôles, groupes), ce qui reste (résultats, fiche athlète), boutons « Annuler » et « Supprimer définitivement ». En cas de 409, le message du backend s'affiche dans la boîte. Succès : invalidation de la session, `router.push("/")`.

## D9. Suppressions simultanées du même compte

**Décision**: aucun verrou dédié. En PostgreSQL, la seconde transaction attend le verrou de ligne posé par le premier `DELETE`, puis ne trouve plus la ligne : SQLAlchemy émet un avertissement (`confirm_deleted_rows`) sans lever, les mises à vide n'affectent aucune ligne, et la seconde requête rend 204. Rien n'est cassé ; une seconde ligne `account.delete` peut apparaître au journal. Non reproductible sous SQLite (verrou de base entière), donc non testé.

## D10. Finir la suppression dans l'annuaire Entra (revue de PR #1357)

**Décision**: la ligne `account.delete` porte `entra_oids`, les `subject` des identités `entra` du compte supprimé. L'exploitant relève chaque mois ces `oid` dans le journal de la base de **production**, nommée explicitement, vérifie à blanc puis supprime chaque utilisateur par Graph (`infra/entra-external-id/AGENTS.md`).

**Rationale**: le tenant sert à la préproduction comme à la production ; comparer l'annuaire à une base, comme le proposait la première version, aurait supprimé les comptes vivants de l'autre environnement. L'`oid` est un identifiant pseudonyme, sans adresse ni nom, gardé 12 mois avec le journal et à cette seule fin.

**Alternatives**: comparaison annuaire contre base (rejetée, voir ci-dessus) ; suppression automatique par Graph (flux *client credentials* payant).
