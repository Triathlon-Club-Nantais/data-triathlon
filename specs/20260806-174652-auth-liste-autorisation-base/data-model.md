# Data model — `allowed_emails`

Une table, quatre colonnes, aucune table existante modifiée. Le schéma est géré
par Alembic ; la révision descend de `f6a7b8c9d0e1` (tête au 2026-08-06).

## La table

| Colonne | Type | Contraintes | Ce qu'elle porte |
| --- | --- | --- | --- |
| `id` | `int` | PK | — |
| `email` | `str` | **`UNIQUE`**, indexé, non nul | L'adresse **normalisée** : minuscules, espaces de bordure retirés |
| `created_at` | `datetime` | défaut `utcnow` | Quand l'adresse a été inscrite |
| `created_by_user_id` | `int \| None` | FK `users.id`, nullable | Qui l'a inscrite — `NULL` quand l'inscription vient de la CLI ou de la reprise |

`created_by` est une `relationship` vers `User` (sens unique, aucune collection
ajoutée sur `User`) : l'écran affiche « ajoutée le … par … », donc quelque chose
la lit — c'est le critère que le modèle `User` pose déjà pour son `athlete_id`,
resté colonne seule faute de lecteur. La liste est chargée en `joinedload` :
trente lignes valent une requête, pas trente et une.

**Pas d'`ondelete`**, au même titre que les trois tables de #114 :
`database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la contrainte serait inerte
en SQLite et active en PostgreSQL. Supprimer l'utilisateur qui a inscrit une
adresse ne doit **jamais** retirer l'adresse : ce serait une révocation d'accès
par effet de bord.

## Trois invariants

1. **L'adresse est rangée normalisée, jamais telle que saisie.** C'est ce qui
   rend `UNIQUE` suffisant et la comparaison de connexion triviale. Sans cette
   normalisation à la source, il faudrait un index fonctionnel `lower(email)`
   côté PostgreSQL, et « `Contributeur@Exemple.FR` » cohabiterait avec
   « `contributeur@exemple.fr` » comme deux entrées distinctes désignant la même
   personne.
2. **La table autorise, elle n'identifie pas.** Aucune colonne ne désigne le
   titulaire, et aucune ne le désignera : une identité externe inconnue crée
   **toujours** un nouvel utilisateur (FR-003 de #114), et apparier sur l'adresse
   rouvrirait la prise de contrôle par pré-inscription. `created_by_user_id`
   nomme celui qui **accorde**, jamais celui qui reçoit.
3. **Elle n'est pas rattachée à une organisation.** Elle répond « cette adresse
   peut-elle ouvrir une session ? », pas « dans quel club ? » — c'est le rôle qui
   porte l'organisation (#115). Une liste par club supposerait de savoir à quel
   club rattacher quelqu'un *avant* qu'il existe, ce que rien ne sait faire.

## Les transitions

```text
absente ──POST /admin/allowed-emails──▶ autorisée ──DELETE /{id}──▶ absente
        └─CLI allow-email ────────────▶           └─(refusé 409 si perte du dernier admin)

Effet de bord symétrique sur les comptes portant l'adresse (users.email, casse ignorée) :
  inscription  →  is_active = True   (sans quoi une réinscription ne rouvrirait rien)
  retrait      →  is_active = False  (ce qui fait tomber les sessions, l'invariant étant une jointure)
```

L'ajout est **idempotent** (contrainte `UNIQUE` rattrapée sous `SAVEPOINT`), le
retrait aussi (ligne absente → succès sans effet).

## Ce que cette table n'enregistre pas

- **Les tentatives de connexion refusées.** Écartées avec leur raisonnement
  complet dans `specs/20260801-145428-auth-socle-sso/data-model.md`, §« Ce
  qu'aucune table n'enregistre », et confirmé hors périmètre par la spec : seule
  écriture pilotée par un visiteur non authentifié, données personnelles de tiers
  non consentants, rendu de texte d'origine externe. Le refus continue de
  **journaliser** l'adresse soumise côté serveur.
- **L'historique des retraits.** Un retrait supprime la ligne ; il n'y a ni
  `removed_at`, ni ligne archivée. Conserver l'adresse d'une personne dont on
  vient de fermer l'accès, sans durée définie et sans que rien ne la lise, serait
  de la donnée personnelle gardée par réflexe.
- **Un motif, une note, un nom.** L'écran affiche l'adresse ; qui elle désigne se
  lit dans la liste des utilisateurs dès la première connexion. Une colonne
  « commentaire » serait du texte libre saisi à la main, à rendre échappé, pour
  un besoin que personne n'a exprimé.
- **Une date d'expiration.** L'accès ne se périme pas tout seul ; le retrait est
  un geste.

## Ce qui change ailleurs, sans migration

| Objet | Changement |
| --- | --- |
| `Settings.auth_allowed_emails` | **supprimé** — et avec lui son validateur CSV partagé avec `cors_origins`, qui ne garde que `cors_origins` |
| `Settings.auth_is_configured` | ne pèse plus que la clé de signature et l'origine de retour |
| `permissions.P` / `permissions.ALL` | + `allowed_emails:manage`, dans la fonctionnalité « Rôles et accès » |
| `user_repository` | + `set_active(db, users, active)` ; la docstring de `list_all` cesse de citer la variable d'environnement |
| `users.is_active` | acquiert son **premier** producteur applicatif (voir `research.md` R4) |
