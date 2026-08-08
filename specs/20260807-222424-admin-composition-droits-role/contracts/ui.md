# Contrat d'interface — `/admin/droits`

Deux contrats, et un seul est nouveau. Celui de l'API est **consommé sans être
modifié** : il est décrit par
[`specs/20260804-214724-auth-rbac-roles/contracts/admin-api.md`](../../20260804-214724-auth-rbac-roles/contracts/admin-api.md),
et rien ici ne le redéfinit. Ce document fixe ce que l'écran promet à l'œil et
au clavier.

## Ce que l'écran appelle

| Geste | Ressource | Pouvoir exigé | Quand |
| --- | --- | --- | --- |
| Charger l'inventaire | `GET /api/v1/admin/permissions` | `roles:read` | au montage, `staleTime: Infinity` |
| Charger les rôles | `GET /api/v1/admin/roles` | `roles:read` | au montage |
| Créer | `POST /api/v1/admin/roles` → 201 | `roles:write` | validation de la boîte de dialogue |
| Recomposer / renommer | `PATCH /api/v1/admin/roles/{id}` | `roles:write` | « Enregistrer » d'un panneau |
| Basculer le statut | `PATCH /api/v1/admin/roles/{id}` | `roles:write` **et** être superutilisateur | geste distinct, confirmé |
| Supprimer | `DELETE /api/v1/admin/roles/{id}` → 204 | `roles:write` | après `window.confirm` |

`GET /api/v1/admin/roles/{id}` n'est **pas** appelée : la liste rend déjà des
`RoleRead` complets, un appel par rôle déplié ne rendrait rien de neuf.

Aucune ressource n'est appelée avec un champ hors contrat : `RoleUpdate` est
`extra="forbid"`, et le type `RoleUpdate` du front ne porte que les quatre
champs acceptés.

## Ce que l'écran rend

### Structure

```text
Droits des rôles                                   [ Créer un rôle ]

┌─ Administrateur          · livré · superutilisateur · 2 porteurs ─┐
│  Franchit tout pouvoir, y compris ceux livrés après lui.          │
│                                                                    │
│  [Rôles et accès] ────────────────────────────────────────────    │
│    ☐ Consulter les rôles                                          │
│      Voir la liste des rôles, leur composition et l'inventaire…   │
│    ☐ Composer les rôles                                           │
│  … (7 fonctionnalités)                                             │
│                                                                    │
│  Suppression indisponible — rôle livré avec l'application.        │
└────────────────────────────────────────────────────────────────────┘
┌─ Validateur              · livré · 0 porteur ─────────────────────┐
└────────────────────────────────────────────────────────────────────┘
```

### Règles de rendu

1. **Le regroupement vient du serveur.** Un `<fieldset>` par entrée de
   `GET /admin/permissions`, dans l'ordre reçu, son `<legend>` portant `feature`
   verbatim. Aucun tri, aucun regroupement, aucun intitulé écrit côté front.
2. **Jamais le code technique seul.** Chaque case porte `label` en étiquette et
   `description` en texte secondaire. Le `code` ne sert qu'aux attributs
   techniques (`id`, `value`, clé de liste) — sauf pour un code périmé, qui n'a
   plus que lui.
3. **Le statut de superutilisateur est une phrase, pas une case.** Un rôle qui
   le porte annonce ce qu'il fait ; sa grille reste affichée mais inerte et
   signalée comme telle — c'est la composition qui redeviendra effective si le
   statut est retiré.
4. **Les codes périmés forment un bloc distinct**, sous la grille, jamais mêlés
   aux cases de l'inventaire, avec la mention qu'ils sont sans effet et qu'ils
   disparaîtront à l'enregistrement de la composition.
5. **Un geste refusé n'est pas offert**, et sa raison est lisible à côté de lui
   — pas seulement dans un `title` : la raison est du texte.

### États d'accessibilité

| Élément | État | Raison affichée |
| --- | --- | --- |
| Case d'un pouvoir non détenu | `disabled`, état courant conservé | « Vous ne portez pas ce pouvoir. » |
| Case d'un pouvoir non détenu, **à la création** | idem — `create_role` soumet l'ensemble complet | idem |
| Toute case d'un rôle superutilisateur | `disabled` | la phrase de statut, au-dessus |
| Bouton « Supprimer », rôle livré | `disabled` | « Rôle livré avec l'application. » |
| Bouton « Supprimer », rôle porté | `disabled` | « Porté par N porteurs. Retirez-le d'abord. » |
| Bascule du statut, sans le porter | non rendue | — |
| Bascule du statut, brouillon en cours | `disabled` | « Enregistrez vos modifications avant de changer le statut. » |
| « Enregistrer », nom vide | `disabled` | le champ le porte |
| « Enregistrer », rôle modifié ailleurs | `disabled` | l'encadré de conflit, au-dessus |
| « Créer le rôle », identifiant hors forme | `disabled` | « L'identifiant commence par une lettre minuscule… » |
| Tout geste d'écriture, sans le pouvoir de composition | non rendu | « Cet écran est en consultation… » |
| « Enregistrer » pendant l'envoi | `disabled` | — |

« N porteurs » est la **même** formule qu'en tête de panneau : l'écran ne compte
pas la même chose de deux façons.

Chaque case est associée à son étiquette par `htmlFor`/`id`. La description est
liée par `aria-describedby`, la raison d'une désactivation également — sans
quoi elle n'existe que pour l'œil.

### Messages d'erreur

| Statut | Titre | Corps |
| --- | --- | --- |
| 401 | Session expirée | « Reconnectez-vous pour consulter les rôles. » |
| 403 | Accès refusé | « Votre rôle ne permet pas de consulter la composition des rôles. Demandez le pouvoir correspondant à un administrateur. » |
| autre | Rôles indisponibles | « Les rôles n'ont pas pu être chargés. Réessayez plus tard. » |

**Une erreur de chargement n'affiche jamais une liste vide** — c'est le défaut
déjà fermé deux fois sur `PendingProvidersTable` puis `AllowedEmailsTable`. Un
refus d'écriture, lui, remonte le message du serveur **verbatim** dans un toast
(`sonner`) : les `DomainError` sont écrites en français pour être lues telles
quelles, et en réécrire une seconde version ferait diverger les deux.

## Navigation

`nav.config.ts`, entrée `u-droits` : `href: "/admin/droits"`, `soon` retiré,
`permission: "roles:write"` inchangé. Le test de `AppNav` qui vérifie qu'une
entrée `soon` n'est pas rendue reste vert : l'entrée cesse d'être `soon`, elle
ne devient pas une exception.
