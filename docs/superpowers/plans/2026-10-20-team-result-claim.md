# Revendication d'un résultat d'équipe : plan d'implémentation (#1739)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un adhérent rattaché retrouve, depuis la colonne de droite de Mon espace, un résultat de relais publié sous un nom d'équipe et demande en un clic à y être ajouté ; le club valide depuis la file existante de #1637.

**Architecture:** on étend `ResultClaim` (#1637) d'une colonne `kind` (`result` | `team`). Un nouvel endpoint membre cherche les relais par nom d'équipe. `approve` choisit son chemin selon `kind` : la sorte `team` passe par `admin_actions.set_teammates` (#894), avec une composition calculée par une fonction pure. Côté front : une carte dans `ColonneDroite`, une troisième pastille `ClaimKind`, une ligne d'équipe dans `ResultClaimsTable`.

**Tech Stack:** FastAPI, SQLAlchemy 2 (sync), Alembic, Pydantic v2, pytest ; Next.js 16, React Query, Vitest + RTL.

**Spec:** `docs/superpowers/specs/2026-10-20-team-result-claim-design.md`

## Global Constraints

- Couches `api → services → repositories` ; seules les repositories construisent des requêtes.
- API `/api/v1` : ajouts seulement (Principe IV). `ResultClaimCreate.kind` a pour défaut `"result"`, donc les appels existants ne changent pas.
- TDD : chaque tâche écrit son test rouge avant le code.
- Copie : français, vouvoiement, « épreuve » et « athlète », jamais « course » ni « coureur » dans un libellé.
- Aucun tiret (—, –, -) pour ponctuer une phrase, ni dans la copie ni dans les commentaires.
- Identifiants, tests et logs en anglais. Commentaires seulement pour une raison non évidente.
- Commits Conventional Commits, sans trailer `Co-Authored-By` ni mention d'IA.
- Hors limites cette semaine (autres sessions) : `frontend/app/(public_restricted)/mon-espace/`, `backend/tests/conftest.py`, `backend/tests/test_auth/conftest.py`, la config pytest et vitest, `.github/workflows/ci.yml`.
- Worktree : une commande git par appel Bash, sans `cd` ; `uv run --project backend …` et `npm --prefix frontend …` remplacent le `cd`.
- **Fiche d'équipe** : une fiche dont `prenom` est vide (après `strip`) et `nom` non vide. Même règle en Python et en SQL.

## Review Focus

1. **Saisie avec accents, majuscules ou caractères `%` et `_`** : « mollets d acier » trouve « LES MOLLETS D'ACIER », et `%` ne joue pas le joker. Test dans la tâche 2.
2. **Compte non rattaché** qui appelle la recherche : il reçoit `[]`, pas une erreur, comme `GET /auth/me/teammates`. Test dans la tâche 2.
3. **Double clic** sur « C'était mon équipe » : une seule demande, qui ne repasse pas en fin de file. Test dans la tâche 3.
4. **Fiche de l'adhérent ayant déjà un résultat sur l'épreuve** : la validation renvoie le refus de `set_teammates` (409, « … a déjà un résultat sur cette épreuve. »), sans rien écrire. Test dans la tâche 4.
5. **Relais marqué sur l'épreuve seulement** (`Course.is_relay` vrai, `Participation.is_relay` faux) : il est trouvé et accepté pour la sorte `team`. Tests dans les tâches 2 et 3.

---

### Task 1: colonne `kind` sur `result_claims`

**Files:**
- Modify: `backend/app/models/result_claim.py`
- Create: `backend/alembic/versions/<rev>_result_claim_kind_1739.py`
- Modify: `backend/app/repositories/result_claim_repository.py` (`replace_pending`)
- Test: `backend/tests/test_migrations.py`, `backend/tests/test_services/test_result_claims.py`

**Interfaces:**
- Produces : `KIND_RESULT = "result"`, `KIND_TEAM = "team"` dans `app/models/result_claim.py` ; `ResultClaim.kind: Mapped[str]` (String(16), non nul, `server_default="result"`) ; `replace_pending(db, *, user_id, participation_id, kind: str = KIND_RESULT) -> ResultClaim`. Une demande renvoyée garde la `kind` reçue (elle écrase l'ancienne dans l'upsert).

- [ ] **Step 1: vérifier la tête Alembic.** `git fetch origin main`, puis `git log origin/main --oneline -- backend/alembic/versions` : si une révision plus récente que `23e9124847d5` est arrivée, la prendre comme `down_revision`.
- [ ] **Step 2: tests rouges.**
  - Dans `test_migrations.py`, sur le modèle de `test_result_claims_table_up_and_down` : `test_result_claim_kind_up_and_down`. Après upgrade, la colonne `kind` existe et une ligne insérée avant l'upgrade vaut `"result"`. Après downgrade, la colonne a disparu.
  - Dans `test_result_claims.py` : `test_a_claim_is_a_result_claim_by_default`, qui vérifie `request_claim(...).kind == KIND_RESULT`.
- [ ] **Step 3: lancer** `uv run --project backend pytest backend/tests/test_migrations.py -k kind backend/tests/test_services/test_result_claims.py -k default -n 0` → FAIL.
- [ ] **Step 4: implémenter** la colonne, la migration (`op.batch_alter_table("result_claims")`, `add_column` avec `server_default="result"`, `nullable=False`) et le paramètre `kind` de `replace_pending`.
- [ ] **Step 5: relancer** → PASS. Puis `uv run --project backend pytest backend/tests/test_services/test_result_claims.py backend/tests/test_api/test_result_claims_api.py` → PASS.
- [ ] **Step 6: commit** `feat(claims): add a kind column to result claims (#1739)`.

### Task 2: chercher un résultat d'équipe

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (nouvelle fonction)
- Modify: `backend/app/services/result_claims.py` (`is_team_record`, `search_team_results`)
- Modify: `backend/app/schemas/athlete_claim.py` (`TeamResultRead`)
- Modify: `backend/app/api/deps.py` (`team_search_rate_limit`, 120 appels par 3 600 s, seau `"team_search"`)
- Modify: `backend/app/api/v1/auth.py` (route)
- Test: `backend/tests/test_repositories/test_team_result_search.py` (nouveau), `backend/tests/test_api/test_result_claims_api.py`

**Interfaces:**
- Produces :
  - `participation_repository.search_team_results(db, *, term: str, exclude_athlete_id: int, limit: int = 10) -> list[Participation]`, avec `course`, `athlete` et `teammate_links.athlete` chargés. Les lignes sont triées par `Course.event_date` décroissante, puis `Participation.id` décroissant.
  - `result_claims.is_team_record(athlete: Athlete) -> bool`.
  - `result_claims.search_team_results(db, user: User, term: str) -> list[TeamResultHit]`, où `TeamResultHit` est un dataclass gelé : `participation: Participation`, `team_name: str`, `teammates: list[str]`.
  - Route `GET /auth/me/team-results?q=` → `list[TeamResultRead]`, avec `q: str = Query(min_length=3, max_length=80)`, `dependencies=[Depends(require_site_access), Depends(team_search_rate_limit)]`.
  - `TeamResultRead{participation_id: int, team_name: str, course_id: int, course_name: str, event_date: str | None, rank_overall: int | None, total_time: str | None, teammates: list[str]}`.
- Règle SQL :
  - **Relais** : `Participation.is_relay` **ou** `Course.is_relay`.
  - **Validé** : `validated_clause(Participation.is_pending_validation)`.
  - **Pas déjà dedans** : `athlete_id != exclude_athlete_id`, et aucun `ParticipationTeammate` de l'adhérent.
  - **Périmètre** : porteur fiche d'équipe **ou** composition existante.
  - **Correspondance** : `unaccent_like(Participation.team_name, motif)`, **ou** porteur fiche d'équipe **et** `unaccent_like(Athlete.nom, motif)`, avec `motif = f"%{escape_like(deaccent(term)).lower()}%"` (helpers d'`athlete_repository`).
- Service :
  - Il rend `[]` si `user.athlete_id is None`.
  - `team_name` vaut `participation.team_name or participation.athlete.nom`.
  - `teammates` est la liste des noms affichés des équipiers (prénom puis nom).
  - Il écarte une ligne dont le porteur ou un équipier a son `identity_hash(nom, prenom)` dans `opposition_repository.all_hashes(db)`, comme `teammate_service`.

- [ ] **Step 1: tests repository** (`test_team_result_search.py`) :
  - `test_finds_a_team_record_by_its_name_ignoring_case_and_accents` : « Les Mollets d'Écume » trouvé par `"mollets d'ecume"`.
  - `test_finds_a_composed_relay_by_team_name`.
  - `test_relay_flag_on_the_course_only_is_enough`.
  - `test_ignores_relays_split_on_person_records` : porteur « GILLES Hugo », `team_name="Tri Again"`, sans composition → absent.
  - `test_ignores_pending_and_rejected_results`.
  - `test_ignores_results_the_member_already_carries_or_belongs_to`.
  - `test_like_wildcards_are_literal` : `"%"` ne trouve rien.
  - `test_at_most_limit_rows_newest_first`.
- [ ] **Step 2: tests API** dans `test_result_claims_api.py` :
  - `test_search_team_results_returns_hits` : forme exacte d'un `TeamResultRead`.
  - `test_search_needs_three_characters` : 422.
  - `test_search_without_claimed_athlete_returns_empty`.
  - `test_search_hides_opposed_identities`.
- [ ] **Step 3: lancer** les deux fichiers → FAIL.
- [ ] **Step 4: implémenter** repository, service, schéma, plafond et route.
- [ ] **Step 5: relancer** → PASS.
- [ ] **Step 6: commit** `feat(claims): search relay results by team name for a claimed member (#1739)`.

### Task 3: demander à rejoindre une équipe

**Files:**
- Modify: `backend/app/services/result_claims.py` (`request_claim`)
- Modify: `backend/app/schemas/athlete_claim.py` (`ResultClaimCreate.kind`, `ResultClaimRead.kind`)
- Modify: `backend/app/api/v1/auth.py` (`request_result_claim` transmet `body.kind`)
- Test: `backend/tests/test_services/test_result_claims.py`, `backend/tests/test_api/test_result_claims_api.py`

**Interfaces:**
- Consumes : `KIND_RESULT`, `KIND_TEAM`, `replace_pending(..., kind=)` (tâche 1).
- Produces :
  - `request_claim(db, user, participation_id, *, kind: str = KIND_RESULT) -> ResultClaim`.
  - `ResultClaimCreate.kind: Literal["result", "team"] = "result"`.
  - `ResultClaimRead.kind: Literal["result", "team"]`.
- Règles :
  - Sorte `result` : inchangée (refuse toujours les relais).
  - Sorte `team` : `UnclaimableResultError` si le résultat n'est pas un relais (`participation.is_relay or participation.course.is_relay`), s'il est en attente de validation, ou si la fiche de l'adhérent en est déjà porteuse ou équipière.
  - Le plafond `MAX_PENDING` et le second clic idempotent sont communs aux deux sortes.

- [ ] **Step 1: tests service** :
  - `test_a_member_asks_to_join_a_team_result` : `kind == KIND_TEAM`, statut en attente, porteur inchangé.
  - `test_a_team_claim_accepts_a_relay_flagged_on_the_course_only`.
  - Paramétré `test_a_team_claim_is_refused` avec les cas `"not_relay"`, `"pending"`, `"already_carrier"`, `"already_teammate"`.
  - `test_a_second_click_on_a_team_claim_keeps_its_place` : même id, une seule ligne.
  - `test_team_and_result_claims_share_the_pending_ceiling`.
- [ ] **Step 2: test API** `test_post_team_claim` : `POST /auth/me/result-claims` avec `{"participation_id": id, "kind": "team"}` → 201, `kind == "team"`. `GET` rend aussi `kind`.
- [ ] **Step 3: lancer** → FAIL. **Step 4: implémenter.** **Step 5: relancer** les deux fichiers → PASS.
- [ ] **Step 6: commit** `feat(claims): let a claimed member ask to join a team result (#1739)`.

### Task 4: valider une demande d'équipe

**Files:**
- Modify: `backend/app/services/result_claims.py` (`team_composition_with`, `CompositionToDecideError`, `approve`, `ResultClaimReview`, `list_pending_with_hints`)
- Modify: `backend/app/schemas/athlete_claim.py` (`ResultClaimReviewRead`)
- Modify: `backend/app/api/v1/admin_athlete_claims.py` (construction du DTO)
- Test: `backend/tests/test_services/test_result_claims.py`, `backend/tests/test_api/test_result_claims_api.py`

**Interfaces:**
- Consumes : `is_team_record` (tâche 2), `admin_actions.set_teammates(db, *, participation_id, teammates, user_id)`, `participation_repository.teammate_athlete_ids`, `exists_for_athlete_on_course`.
- Produces :
  - `team_composition_with(current: list[Athlete], carrier: Athlete, claimant_id: int) -> list[int] | None`. C'est une fonction pure, `None` voulant dire « l'admin tranche ».
  - `class CompositionToDecideError(DomainError)`, statut 409, message exact : `« La composition de cette équipe a été posée à la main : composez l'équipe dans « Attribuer aux équipiers », puis validez la demande. »`.
  - `ResultClaimReview` gagne quatre champs : `kind: str`, `teammates: list[Athlete]` (composition actuelle, vide sans composition), `proposed_teammates: list[Athlete] | None` (résultat de `team_composition_with`, `None` pour la sorte `result`) et `claimant_has_result_on_course: bool`.
  - `ResultClaimReviewRead` gagne `kind: Literal["result","team"]`, `teammates: list[ClaimedAthleteRead]`, `proposed_teammates: list[ClaimedAthleteRead] | None` et `claimant_has_result_on_course: bool`.
- `team_composition_with` :
  1. Sans composition : `[claimant_id, carrier.id]` si `is_team_record(carrier)`, sinon `None`.
  2. Avec composition sans fiche d'équipe : `None`.
  3. Sinon, `ids` = ids actuels dans l'ordre. S'il reste au moins un équipier qui n'est pas une fiche d'équipe, la première fiche d'équipe est remplacée **à sa place** par `claimant_id`. Sinon `claimant_id` est ajouté en fin de liste.
- `approve` pour la sorte `team` :
  - Si la fiche de l'adhérent est déjà porteuse ou équipière, la demande est close, sans écriture sur le résultat (cas d'une composition faite à la main).
  - Sinon, `team_composition_with` ; `None` lève `CompositionToDecideError` ; une liste est passée à `set_teammates(..., user_id=actor_id)`.
  - Puis `delete_claim` et `audit.record(action="result_claim.approve_team", entity_type="participation", entity_id=participation_id, payload={"user_id", "athlete_id", "claim_id"})`.
  - La sorte `result` reste inchangée.

- [ ] **Step 1: tests de la fonction pure**, `test_team_composition_with`, paramétré :
  - non composé + porteur fiche d'équipe T → `[C, T]` ;
  - non composé + porteur personne → `None` ;
  - `[A, T]` → `[A, C]` ;
  - `[T, A]` → `[C, A]` ;
  - `[A, B]` → `None` ;
  - `[T1, T2]` → `[T1, T2, C]`.
- [ ] **Step 2: tests d'approbation** :
  - `test_approving_a_first_team_claim_keeps_the_team_record` : composition `[C, T]`, porteur C, `team_name` = nom de T, T non purgée.
  - `test_approving_the_partner_replaces_the_team_record` : `[A, B]`, T purgée.
  - `test_approving_a_hand_composed_team_asks_the_admin` : 409 `CompositionToDecideError`, demande toujours en attente.
  - `test_approving_after_the_admin_added_the_member_closes_the_claim` : demande supprimée, composition inchangée.
  - `test_approving_refuses_a_member_who_already_ran_the_course` : 409 `DuplicateError`, demande en attente, rien d'écrit.
  - `test_review_hints_for_a_team_claim` : `teammates`, `proposed_teammates`, `claimant_has_result_on_course`.
- [ ] **Step 3: test API** `test_queue_shows_team_claims_with_their_composition` : forme JSON des quatre nouveaux champs, et `kind == "result"` sur une demande existante.
- [ ] **Step 4: lancer** → FAIL. **Step 5: implémenter.** **Step 6: relancer** `uv run --project backend pytest -m "not integration"` → PASS, et `uv run --project backend ruff check backend` → propre.
- [ ] **Step 7: commit** `feat(claims): approve a team claim by adding the member to the relay composition (#1739)`.

### Task 5: client, types et pastille

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api/client.ts`, `frontend/lib/queries/auth.ts`, `frontend/lib/queries/keys.ts`
- Modify: `frontend/components/admin/ClaimKind.tsx`, `frontend/lib/admin-action-log.ts`
- Test: `frontend/components/admin/ClaimKind.test.tsx` (nouveau ou existant), test du libellé dans le test existant d'`admin-action-log` s'il existe

**Interfaces:**
- Consumes : routes et DTO des tâches 2 à 4.
- Produces :
  - `TeamResult` dans `types.ts`, miroir de `TeamResultRead`.
  - `ResultClaim.kind: "result" | "team"`.
  - `ResultClaimReview` gagne `kind`, `teammates: ClaimedAthlete[]`, `proposed_teammates: ClaimedAthlete[] | null` et `claimant_has_result_on_course: boolean`.
  - `apiClient.searchMyTeamResults(q: string): Promise<TeamResult[]>`.
  - `apiClient.requestResultClaim(participationId: number, kind: "result" | "team" = "result")`.
  - `queryKeys.myTeamResults(q: string)`.
  - `useMyTeamResults(q: string, enabled: boolean)`.
  - `useRequestResultClaim()` prend `{ participationId: number; kind?: "result" | "team" }`, et ses appelants existants sont mis à jour (`ResultClaimAction.tsx`).
  - `ClaimKind({ kind }: { kind: "record" | "result" | "team" })` : `team` → icône lucide `Users`, libellé exact « Résultat d'équipe ».
  - Libellé `"result_claim.approve_team": "Résultat d'équipe ajouté à la fiche de son auteur"`.

- [ ] **Step 1: test rouge** `ClaimKind` : `kind="team"` affiche « Résultat d'équipe ». **Step 2: lancer** `npm --prefix frontend test -- components/admin/ClaimKind` → FAIL.
- [ ] **Step 3: implémenter**, puis `npm --prefix frontend test -- components/participations/ResultClaimAction components/admin` → PASS.
- [ ] **Step 4: commit** `feat(frontend): client, types and badge for team result claims (#1739)`.

### Task 6: carte « Un résultat d'équipe manque ? » dans Mon espace

**Files:**
- Create: `frontend/components/mon-espace/ResultatEquipeManquant.tsx`
- Modify: `frontend/components/mon-espace/ColonneDroite.tsx` (rendue après `MesCoequipiers`)
- Test: `frontend/components/mon-espace/ResultatEquipeManquant.test.tsx`, `frontend/components/mon-espace/ColonneDroite.test.tsx`

**Interfaces:**
- Consumes : `useMyTeamResults`, `useMyResultClaims(true)`, `useRequestResultClaim` (tâche 5).
- Produces : `ResultatEquipeManquant()`, sans props (la colonne n'est rendue que pour un compte rattaché).
- Rendu : `Card padding={20}`, `Eyebrow`, `Input`, `Button`, `Alert`, `AnnonceStatut` de `@/components/tcn`, sur le modèle de `MesCoequipiers`.
- Copie exacte :
  - eyebrow « Un résultat d'équipe manque ? » ;
  - texte « Swimrun, raid, relais : cherchez le nom de votre équipe. » ;
  - champ libellé « Nom de l'équipe » ;
  - bouton « Chercher » ;
  - vide « Aucun résultat d'équipe ne correspond à « {q} ». » ;
  - bouton de ligne « C'était mon équipe », `aria-label` « C'était mon équipe : {team_name}, {course_name} » ;
  - en attente « Demande envoyée, le club va vérifier. » ;
  - refusée « Demande refusée par le club. », le bouton restant offert pour la renvoyer.
- Comportement :
  - Recherche à la soumission du formulaire (Entrée ou « Chercher »), le bouton étant inerte sous 3 caractères.
  - Une ligne affiche `team_name`, `course_name`, la date formatée, le rang, le temps et les équipiers.
  - L'état d'une ligne vient de `useMyResultClaims` (correspondance `participation_id`, `kind === "team"`).
  - Le refus serveur s'affiche dans `Alert` avec son message.
  - Squelette sur `isPending` d'une recherche active, jamais sur `isLoading` (`frontend/AGENTS.md`).

- [ ] **Step 1: tests rouges** :
  - `cherche_par_nom_et_affiche_les_lignes` ;
  - `bouton_chercher_inerte_sous_trois_caracteres` ;
  - `etat_vide_cite_la_saisie` ;
  - `un_clic_envoie_une_demande_d_equipe` (`requestResultClaim` appelé avec `(id, "team")`, puis la ligne affiche « Demande envoyée, le club va vérifier. ») ;
  - `une_demande_refusee_peut_etre_renvoyee` ;
  - `le_refus_du_serveur_s_affiche`.
  - Dans `ColonneDroite.test.tsx` : la carte est présente.
- [ ] **Step 2: lancer** `npm --prefix frontend test -- components/mon-espace` → FAIL. **Step 3: implémenter.** **Step 4: relancer** → PASS.
- [ ] **Step 5: commit** `feat(mon-espace): find a missing team result and ask to join it (#1739)`.

### Task 7: la file du back-office traite les demandes d'équipe

**Files:**
- Modify: `frontend/components/admin/ResultClaimsTable.tsx`
- Test: `frontend/components/admin/ResultClaimsTable.test.tsx`

**Interfaces:**
- Consumes : `ResultClaimReview` étendu (tâche 5), `TeammatesDialog({ resultat: {id, epreuve, date}, equipiers, onClose })` de `components/athletes/TeammatesDialog.tsx`, `useDecideResultClaim()`.
- Rendu d'une ligne `kind === "team"` :
  - pastille `<ClaimKind kind="team" />` ;
  - colonne « Déplacement » : « Équipe actuelle : {noms} » (ou « Fiche d'équipe : {current_athlete} » sans composition) ;
  - puis « Après validation : {noms de proposed_teammates} », ou « À composer : la composition a été posée à la main. » quand `proposed_teammates` vaut `null` ;
  - et « Cet athlète a déjà un résultat sur cette épreuve. » si `claimant_has_result_on_course`.
- Boutons d'une ligne d'équipe :
  - « Ajouter à l'équipe » (approve) quand `proposed_teammates` n'est pas `null` ;
  - sinon « Composer l'équipe », qui ouvre `TeammatesDialog` prérempli avec `teammates` (ou `[current_athlete]` sans composition) suivi de `claimant_athlete`, puis « Clore la demande » (approve) ;
  - « Refuser » inchangé.
- Le message d'un 409 s'affiche comme les refus actuels de la table. Les lignes `kind === "result"` ne changent pas.

- [ ] **Step 1: tests rouges** :
  - `une_demande_d_equipe_montre_la_composition_proposee` ;
  - `ajouter_a_l_equipe_valide_la_demande` ;
  - `une_equipe_composee_a_la_main_ouvre_la_fenetre_preremplie` (équipiers puis demandeur) ;
  - `une_demande_de_resultat_reste_inchangee`.
- [ ] **Step 2: lancer** `npm --prefix frontend test -- components/admin/ResultClaimsTable` → FAIL. **Step 3: implémenter.** **Step 4: relancer** `npm --prefix frontend test`, `npm --prefix frontend run lint`, `npm --prefix frontend run build` → verts.
- [ ] **Step 5: commit** `feat(admin): review team result claims in the claims queue (#1739)`.
