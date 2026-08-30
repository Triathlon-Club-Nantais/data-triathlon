# Research: Déclaration de bénévolat

## D1 — Sur quelle entité clé la déclaration (`User` ou `Athlete`) ?

**Decision**: `User` (déclarant et bénéficiaire sont tous deux des
`users.id`), jamais `Athlete`.

**Rationale**: le geste est fait par une personne connectée (session cookie,
`current_user`) — la seule identité fiable côté serveur. `User.athlete_id`
existe mais est nullable, ne porte aucune `relationship` et « aucune route
existante n'en dépend » (docstring de `app/models/user.py`) : rien ne garantit
qu'un membre connecté ait un athlète lié. Le seul mécanisme « athlète retenu »
du produit (`AthleteSelection`, `components/layout/AthletePicker`) est un
**bookmark client-side** (`localStorage`), pas une identité serveur — il ne
peut pas fonder une autorisation. Quand un admin déclare pour un tiers, il
choisit donc parmi les `User` existants (patron déjà en place : `USERS_READ`,
« voir la liste des personnes connectées au moins une fois », page
`/admin/utilisateurs`), pas parmi les fiches `Athlete`.

**Alternatives considered**: clé sur `Athlete` comme `VolunteerAction`
(#709) — rejetée : casserait le self-service pour tout membre sans athlète
lié, et mélangerait deux univers (roster de résultats de course vs comptes
applicatifs) que #709 avait déjà distingués pour son propre besoin (quota de
saison, où l'athlète est la bonne clé).

## D2 — Indépendance vis-à-vis de `VolunteerAction` (#709/#741)

**Decision**: nouvelle table `volunteer_declarations`, aucun lien de code ou
de données avec `volunteer_actions`. Tranché avec l'utilisateur (voir
spec.md § Assumptions).

**Rationale**: `VolunteerAction` est un journal immuable (« plusieurs lignes
peuvent coexister… un journal, pas un indicateur unique »), déclaré
exclusivement par un admin, sans titre/description, au service d'un calcul
de quota déjà livré et testé. Réutiliser ou étendre ce modèle pour porter la
suppression et le statut « en attente » de cette feature romprait son
invariant documenté et risquerait une régression sur du code livré le jour
même. Une table séparée coûte une migration de plus, mais élimine tout
couplage accidentel.

**Alternatives considered**: fusion des deux modèles (rejetée par
l'utilisateur — risque le plus élevé) ; lien automatique validation →
création d'un `VolunteerAction` (rejeté — hors périmètre de l'issue #751,
Principe VI/YAGNI : rien ne demande aujourd'hui qu'une déclaration validée
compte pour le quota de saison).

## D3 — Permissions : quel(s) pouvoir(s) ajouter à `app/core/permissions.py` ?

**Decision**: deux pouvoirs, sur le patron déjà établi par
`PENDING_PROVIDERS_READ`/`_HANDLE` et `FEEDBACK_READ`/`_MANAGE` (séparer
consultation d'ensemble et geste d'administration), sous une nouvelle
fonctionnalité `FEATURE_VOLUNTEERING = "Déclarations de bénévolat"` :

- `benevolat:read` — consulter la vue d'ensemble (toutes les déclarations,
  tous membres).
- `benevolat:manage` — créer pour un tiers, valider une déclaration en
  attente, supprimer la déclaration d'un tiers.

**Rationale**: toute création/consultation **de sa propre** déclaration ne
passe par aucun pouvoir — seule une session valide (`current_user`) est
requise, comme le reste du site pour les gestes qui ne portent que sur ses
propres données. Séparer `read`/`manage` suit le patron déjà répété deux fois
dans le catalogue plutôt que d'introduire une troisième forme (ex. un pouvoir
unique) sans raison.

**Alternatives considered**: réutiliser `ATHLETES_VOLUNTEER_MANAGE` — rejeté,
ce pouvoir est explicitement scopé au quota de saison (#709) et son libellé
le dit ; le réutiliser pour un tout autre workflow romprait la lisibilité du
catalogue qu'un commentaire de `permissions.py` défend déjà (« Distinct de la
validation de saison »).

## D4 — Faut-il tracer les gestes admin dans `AdminActionLog` ?

**Decision**: oui, pour les trois gestes admin uniquement — créer pour un
tiers, valider, supprimer la déclaration d'un tiers — jamais pour les gestes
d'un membre sur sa propre déclaration.

**Rationale**: patron déjà en place (`admin_actions.declare_volunteer_action`,
`validate_season`, corrections `athlete.update`…) : tout geste qui modifie la
donnée **d'un tiers** est journalisé (`action`, `entity_type`, `entity_id`,
`payload`). Un membre qui crée ou supprime sa propre déclaration n'est pas un
geste d'administration — même patron que `UserFeedback`, dont la soumission
publique n'est pas journalisée dans `AdminActionLog`.

## D5 — Statut : colonne ou table à part ?

**Decision**: une colonne `status` (`String`, valeurs `"en_attente"` /
`"validee"`), sur le patron exact de `UserFeedback.status`
(`FEEDBACK_STATUSES`, transitions libres, pas de table de statuts séparée).

**Rationale**: deux valeurs seulement, pas de workflow à plusieurs étapes ni
de métadonnée par statut — une table séparée serait une indirection
spéculative (Principe VI). Contrairement à `SeasonValidation`, où « l'existence
de la ligne porte le statut » a un sens (validable/dévalidable en toggle),
ici la ligne existe dès la création (en_attente) et ne change que d'état,
jamais d'existence pour ce qui est de la validation — la colonne est donc le
choix qui correspond au cycle de vie réel.

## D6 — Suppression : soft-delete ou `DELETE` réel ?

**Decision**: suppression physique (`DELETE FROM volunteer_declarations`),
comme le reste du produit hors `AdminActionLog`/journal.

**Rationale**: FR-008 du spec est explicite — « ne laisser subsister aucune
trace consultable ». Un soft-delete (`deleted_at`) laisserait une trace en
base, contraire à l'intention exprimée par l'issue (contraste assumé avec
`AdminActionLog`).
