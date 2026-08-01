# Data Model — Socle d'authentification SSO (#114)

Phase 1. Trois tables nouvelles, **aucune table existante modifiée**. Une seule révision Alembic.

Conventions reprises de l'existant (`athlete.py`, `participation.py`, `course.py`) : contraintes
nommées `uq_*`, `created_at` alimenté par `app.core.time.utcnow` (jamais `datetime.utcnow` ni
`func.now()`), colonnes `DateTime` naïves en UTC, clés étrangères indexées et **sans** `ondelete`.

---

## `users` — l'identité applicative

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `int` | PK | |
| `email` | `str` | non nul, indexé, **non unique** | Adresse de contact, rafraîchie depuis le fournisseur. |
| `is_active` | `bool` | non nul, défaut `True` | Une désactivation ferme immédiatement toutes les sessions (FR-015). |
| `created_at` | `datetime` | non nul, défaut `utcnow` | |
| `athlete_id` | `int \| None` | FK `athletes.id`, indexé, nullable | Rattachement facultatif, prévu mais non exploité ici. |

**`email` n'est délibérément pas unique.** C'est l'expression en base de FR-003 : deux identités
externes portant la même adresse donnent **deux** utilisateurs distincts. Poser un `UNIQUE` ici
forcerait un appariement par adresse et rouvrirait la prise de contrôle par pré-inscription
(cf. `research.md` §4). Ne pas « corriger » cette absence.

Pas d'`ondelete` sur `athlete_id` : `database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la
contrainte serait inerte en SQLite et active en PostgreSQL (`research.md` §11). La relation vers
`Athlete` est déclarée `lazy="raise"` — rien dans cette feature ne la lit, et un accès accidentel
doit échouer bruyamment plutôt que d'émettre une jointure sur chaque requête authentifiée.

**Accueille sans restructuration** : `role` (#115).

---

## `identities` — un moyen de se connecter

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `int` | PK | |
| `user_id` | `int` | FK `users.id`, non nul, indexé | |
| `provider` | `str` | non nul | Identifiant court du moyen de connexion (`github`). |
| `subject` | `str` | non nul | Identifiant **opaque** chez le fournisseur. Stocké en `str` : un entier déborderait sur certains dialectes et n'est pas la forme de tous les fournisseurs. |
| `email` | `str` | non nul | Adresse **constatée chez ce fournisseur**, distincte de `users.email`. |
| `secret_hash` | `str \| None` | nullable | Vide pour une identité déléguée. Accueille le futur mot de passe. |
| `created_at` | `datetime` | non nul, défaut `utcnow` | |

**Contrainte** : `UniqueConstraint("provider", "subject", name="uq_identity_provider_subject")`.

C'est la **seule** clé de résolution (FR-002). Une ligne d'`identities` = un moyen de connexion,
révocable unitairement — ce qui est la raison pour laquelle le futur mot de passe vit **ici** et non
sur `users` : « supprimer ma connexion par mot de passe » doit être la suppression d'une ligne, pas
la mise à nul d'une colonne sur l'utilisateur.

Plusieurs identités peuvent pointer un même utilisateur. **Aucune n'est créée automatiquement à
partir d'une autre** : cette feature n'en crée jamais qu'une, à la première connexion.

---

## `user_sessions` — la preuve qu'un navigateur agit pour un utilisateur

| Colonne | Type | Contraintes | Rôle |
| --- | --- | --- | --- |
| `id` | `int` | PK | Ne franchit **jamais** l'API (identifiant séquentiel, énumérable). |
| `user_id` | `int` | FK `users.id`, non nul, indexé | |
| `token_hash` | `str` | non nul, **unique**, indexé | SHA-256 hexadécimal du jeton opaque. |
| `expires_at` | `datetime` | non nul, indexé | |
| `created_at` | `datetime` | non nul, défaut `utcnow` | |

**Contrainte** : `UniqueConstraint("token_hash", name="uq_user_session_token")`.

Nommée `user_sessions` et non `sessions` : `Session` désignerait deux choses dans des modules qui
importent aussi SQLAlchemy.

Le jeton brut n'existe qu'en mémoire et dans le cookie. La base n'en garde que l'empreinte
(FR-012). Une garde refuse d'ouvrir une session sur un jeton de moins de 43 caractères — c'est elle
qui rend SHA-256 nu suffisant, et non l'algorithme (`research.md` §3).

**Trois colonnes délibérément absentes**, toutes ajoutables plus tard par migration purement
additive : `last_seen_at` (une écriture par requête authentifiée pour zéro lecteur),
`user_agent` (donnée quasi personnelle sans durée de conservation), et `revoked_at` — la
déconnexion **supprime** la ligne, un effacement logique ne payant que pour un écran « mes
sessions » (#117) qui n'est pas livré.

---

## Invariant de validité — vérifié par test

Une session est acceptée **si et seulement si** les trois conditions suivantes sont réunies
(FR-013) :

1. une ligne `user_sessions` porte l'empreinte du jeton présenté ;
2. `expires_at` est dans le futur ;
3. l'utilisateur joint est `is_active`.

La troisième condition est une **jointure**, jamais un cache : c'est elle qui rend FR-015 vrai sans
avoir à parcourir les sessions à la désactivation. La désactivation d'un compte ferme donc ses
sessions **immédiatement**, y compris celles déjà en cours.

---

## Cycle de vie

```text
Connexion réussie
  └─ résolution (provider, subject)
       ├─ identité connue  → utilisateur existant, email rafraîchi
       └─ identité inconnue → NOUVEL utilisateur + NOUVELLE identité
                              (même si l'email existe déjà — FR-003)
  └─ suppression des sessions expirées de cet utilisateur (hygiène opportuniste)
  └─ création d'une session : jeton opaque en mémoire, empreinte en base

Requête authentifiée
  └─ empreinte du jeton → ligne → non expirée → utilisateur actif → utilisateur

Déconnexion
  └─ SUPPRESSION de cette ligne seule (les autres appareils survivent — FR-014)

Désactivation d'un compte
  └─ is_active = False → toutes ses sessions cessent d'être acceptées (FR-015)
     et un moyen d'exploitation permet d'en supprimer les lignes (FR-016)
```

---

## Migration Alembic

Une révision, trois `create_table`, aucune modification de table existante (FR : le site public
reste intact). La révision doit être relue à la main après génération, conformément aux contraintes
additionnelles de la constitution.

**Deux points à ne pas oublier**, sans quoi l'échec est obscur :

- `app/models/__init__.py` doit importer et exporter les trois modèles. `tests/conftest.py` fait
  `import app.models` puis `Base.metadata.create_all(...)` : sans cet import, les tables n'existent
  pas dans la base de test.
- Les contraintes doivent être **nommées** (`uq_identity_provider_subject`,
  `uq_user_session_token`), faute de quoi la révision descendante est indéterminée sur SQLite.

La révision est vérifiée en `upgrade` → `downgrade` → `upgrade`, comme le fait déjà
`tests/test_migrations.py`.
