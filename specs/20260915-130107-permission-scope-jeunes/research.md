# Research: Pouvoir « jeunes »

Pas de `NEEDS CLARIFICATION` en sortie de `spec.md` : le périmètre est étroit
et le patron à suivre existe déjà dans le dépôt (32 pouvoirs précédents). Ce
document consigne les décisions de conception, pas une levée d'inconnues
techniques.

## Décision 1 — Granularité : deux codes (`read`/`write`), pas un par sous-fonctionnalité

**Décision** : `jeunes:read` (consulter profils + calendrier) et
`jeunes:write` (créer/modifier profil, tenir le calendrier, faire l'appel,
journal de bord).

**Rationale** : les trois sous-issues de l'epic (#867 profils, #868
calendrier, #869 appel) sont étroitement couplées — l'appel peuple le
calendrier et ouvre le profil du jeune depuis le même écran mobile. Le patron
`athletes:read`/`athletes:write` et `groups:read`/`groups:write`, déjà dans le
catalogue, applique la même règle à des domaines eux aussi composés de
plusieurs écrans (fiche coureur, validation de saison, bénévolat pour
`athletes`). Le principe VI (Simplicité/YAGNI) et FR-042 (« un pouvoir que
rien ne vérifie est un mensonge d'écran », `permissions.py`) convergent vers
le plus petit ensemble qui couvre le besoin exprimé par l'issue (« lecture
profil, écriture profil/appel »).

**Alternatives envisagées** :
- *Un code par sous-fonctionnalité* (`jeunes:profils_read`,
  `jeunes:profils_write`, `jeunes:calendrier_read`, `jeunes:calendrier_write`,
  `jeunes:appel_write`, …) — rejeté : aucun cas d'usage exprimé ne demande de
  donner l'appel sans le calendrier, ou le calendrier sans les profils ; ce
  découpage multiplierait les cases à cocher sans bénéfice mesuré, et le
  catalogue reste ouvert à un raffinement futur si un besoin d'exploitation le
  justifie (ajout de code, jamais une migration — `roles`/`role_permissions`
  sont éditables à chaud).
- *Un seul code* (`jeunes:manage`, tout-ou-rien) — rejeté : casse le patron
  `read`/`write` uniforme du catalogue, et empêche de donner à un bénévole la
  consultation seule (utile pour un accompagnant qui n'anime pas la séance)
  sans lui ouvrir l'écriture du journal de bord, personnel et sensible.

## Décision 2 — La suite de tests reste verte malgré l'absence de garde

**Décision** : documenter, dans `tests/test_permissions_catalogue.py`, une
liste explicite et nominative des pouvoirs dont la garde est posée par une
sous-issue distincte, avec la référence de cette sous-issue en commentaire.
Le test générique (`test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource`)
saute ces entrées précises au lieu de les échouer, et continue d'échouer pour
tout autre pouvoir non gardé.

**Rationale** : FR-004 de `spec.md`. Le méta-test protège une propriété réelle
(FR-026 : « un pouvoir que rien ne vérifie est un mensonge d'écran ») que
cette issue ne peut pas satisfaire seule — elle est explicitement scindée de
la garde par le découpage de l'epic (#863 → #866/#867/#868/#869). Le choix
retenu rend le compromis **auditable** (une entrée par code, une issue de
suivi citée) plutôt que silencieux (test rouge ignoré en CI) ou trompeur
(garde factice posée sur une ressource sans rapport pour faire passer le
test). C'est le même compromis que celui déjà documenté dans le docstring du
fichier de test pour `roles:*`/`users:read`/`quality:override`, nés en US3/US5
de #115 avant que leur garde n'existe — formalisé ici en liste explicite
plutôt qu'en état transitoire non outillé, parce que ce découpage-ci traverse
plusieurs PR fusionnées séparément (`docs/gestion-de-projet.md`, « Workflow
git d'une epic multi-issues ») et que la CI tourne sur chacune.

**Alternatives envisagées** :
- *Laisser le test rouge* — rejeté : la constitution (section CI) et les
  instructions de la tâche exigent une suite verte avant merge ; `ci.yml` se
  déclenche sur `pull_request` quelle que soit la branche cible, donc chaque
  PR de l'epic serait rouge sans ce traitement.
- *Ajouter une route jeunes minimale rien que pour satisfaire le test* —
  rejeté : violerait explicitement le hors-périmètre de l'issue (« Toute
  route/UI jeunes… pas cette issue ») et anticiperait un modèle de données
  (#867) qui n'est pas encore conçu.
- *Affaiblir le test pour tout le catalogue* (ex. le rendre `xfail` global,
  ou ignorer les pouvoirs sans garde silencieusement) — rejeté : viderait la
  garantie FR-026 pour les 32 pouvoirs existants, bien au-delà du besoin de
  cette issue.

## Décision 3 — Aucune modification du mécanisme d'administration existant

**Décision** : aucune ligne touchée dans `app/api/v1/admin_roles.py`,
`app/schemas/`, ni le frontend `/admin/roles`.

**Rationale** : `GET /admin/permissions` sert `permissions.grouped_by_feature()`
et le `PATCH` de composition accepte tout code présent dans `permissions.CODES`
— les deux mécanismes sont déjà génériques par construction (vérifié en
lisant `app/api/v1/admin_roles.py`), exactement le comportement voulu par
FR-002/FR-003 de `spec.md`. Ajouter deux membres à `P`/`ALL` suffit.
