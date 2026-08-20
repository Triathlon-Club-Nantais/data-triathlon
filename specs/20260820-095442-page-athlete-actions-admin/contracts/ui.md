# Contrat d'interface — page `/athletes/[id]` (#439)

Ce que la page doit offrir, à qui, et ce qu'elle ne doit **jamais** offrir. C'est
le contrat que les tests vitest vérifient.

## Table de visibilité — la règle « si et seulement si »

| Action | Emplacement | Pouvoir(s) exigé(s) |
| --- | --- | --- |
| Corriger l'identité (nom, prénom) | en-tête de la fiche | `athletes:write` |
| Corriger la date de naissance | même formulaire, **champ conditionnel** | `athletes:write` **et** `athletes:read` |
| Corriger le club actuel | même formulaire | `athletes:write` |
| Supprimer un résultat | sous chaque ligne du tableau | `participations:delete` |
| Rattacher un résultat | sous chaque ligne du tableau | `participations:reassign` **et** `athletes:read` |

Deux gestes exigent **deux** pouvoirs, et pour la même raison : ils ont besoin de
la recherche ou de la lecture d'identité complète, que seul `athletes:read`
ouvre (research.md, D6 et D7). Sans elle, le geste serait annoncé puis échouerait
en `403` — ce que FR-006 proscrit.

**La même règle vaut dans le back-office.** `components/admin/CourseParticipationsDialog.tsx`
n'exige aujourd'hui que `participations:reassign` pour montrer la réattribution,
alors que son sélecteur appelle la ressource gardée par `athletes:read` : il
annonce un geste qui finit en `403`. Il s'aligne sur cette table (FR-020,
US4-AC3, research.md D6). Une règle de visibilité par geste, pas par écran.

### Divergences relevées dans le code (T018)

Le contrat suit le terrain. Relevé au moment de l'implémentation, sur les
seize gardes de visibilité du front (`grep permissions.includes`) :

| Emplacement | Constat | Suite |
| --- | --- | --- |
| `components/admin/CourseParticipationsDialog.tsx:45` | « Rattacher » n'exige que `participations:reassign`, alors que son sélecteur lit la ressource gardée par `athletes:read`. Aucun message : le geste s'ouvre puis échoue. | **Corrigé** par cette branche (FR-020, US4-AC3). |
| `components/admin/CourseParticipationsDialog.tsx:47` | « Corriger le coureur » n'exige que `athletes:write` et charge lui aussi la fiche gardée par `athletes:read`. | **Laissé tel quel** : la divergence est assumée et déjà outillée — `fiche.isError` rend un message français qui **nomme le pouvoir manquant** (l. 93-97). Ce n'est pas un 403 muet, c'est une dégradation explicite. La rendre invisible retirerait à l'opérateur la seule indication de ce qu'il lui manque. |
| `components/athletes/AthleteAdminPanel.tsx` | Conforme : `athletes:write` pour le formulaire, `athletes:read` pour le seul champ date de naissance. | — |

La différence de traitement entre les deux lignes du back-office n'est pas une
incohérence : « Rattacher » sans `athletes:read` n'offre **rien** à faire (le
sélecteur est vide, il n'y a pas de repli), tandis que « Corriger le coureur »
ouvre un geste dont l'échec est déjà expliqué à l'écran.

L'évaluation est **action par action**. Il n'existe pas d'échelon
« administrateur » : porter `participations:delete` sans `athletes:write` donne
exactement l'action de suppression, et rien d'autre.

## Les quatre états de session (SC-003)

| État | Ce que la page affiche |
| --- | --- |
| **Anonyme** | la page publique, strictement inchangée. Aucun appel réseau de session (le cookie témoin `tcn_logged_in` est absent). |
| **Connecté, aucun des 4 pouvoirs** | la page publique, strictement inchangée. |
| **Un seul des pouvoirs** | exactement l'action correspondante — **sauf pour un pouvoir couplé** : `participations:reassign` seul n'offre **rien**, et `athletes:write` seul offre les corrections **sans** le champ date de naissance. |
| **Session illisible** (erreur de lecture) | aucune action. Une session illisible **n'est pas** une session sans pouvoirs, et l'écran n'affirme ni l'un ni l'autre (FR-008). |

Le quatrième état est déjà tenu par l'infrastructure : `useSession()` est en
`retry: false`, donc une session illisible ressort en **erreur** et non en
« null », et un `permissions.includes(...)` sur une erreur rend `false`.

## Emplacements

### En-tête — `AthleteAdminPanel`

Un accès unique aux corrections de la fiche, monté à côté du nom du coureur.
Ouvre une modale `tcn/Modal` portant, dans un seul formulaire : nom, prénom,
club, et — sous `athletes:read` seulement — date de naissance.

**Le créneau d'en-tête est déjà occupé.** `SelectAthleteButton` y est poussé à
droite par un `marginLeft: "auto"` dans un en-tête en `flexWrap: "wrap"`
(`app/athletes/[id]/page.tsx:73-75`). `AthleteAdminPanel` partage ce créneau : il
se monte **à côté** de ce bouton, sans lui reprendre son `marginLeft: "auto"` — un
second `auto` séparerait les deux commandes aux deux bouts de la ligne. Sur
mobile, l'en-tête passe à la ligne : les deux commandes doivent y rester
côte à côte, pas empilées seules.

**Un seul formulaire pour l'identité et le club**, parce qu'un seul pouvoir les
garde (`athletes:write`) et qu'un seul appel les écrit. Deux modales séparées
feraient deux `PATCH` là où un suffit, et compteraient deux interactions au lieu
d'une (SC-002 : au plus 2).

### Sous chaque ligne du tableau — `ParticipationAdminActions`

Les deux actions par résultat se rendent dans une **sous-ligne**, sœur de celle
qui porte déjà le lien « Voir la preuve ».

> **Contrainte structurelle** : la ligne entière est un `<Link>`. Un `<button>` à
> l'intérieur d'une ancre est du HTML invalide — c'est la raison pour laquelle le
> lien de preuve occupe déjà une sous-ligne. Les actions suivent le même
> placement (research.md, D9).

La grille de sept colonnes de la ligne n'est pas touchée. La sous-ligne
n'apparaît que si au moins une des deux actions est visible : aucun espace
réservé pour un porteur sans pouvoir, aucune ligne vide.

## Confirmations et messages

Tous en français (FR-017).

### Suppression — confirmation obligatoire

La confirmation **nomme l'épreuve** et **dit l'irréversibilité**. Rien n'est
supprimé avant confirmation (FR-011, SC-006 : zéro suppression en une seule
interaction).

```text
Supprimer ce résultat ?

« Triathlon de Nantes — 15 juin 2025 » sera définitivement retiré
de la fiche de Jean-Marc Lemée. Cette action est irréversible.

                                    [ Annuler ]  [ Supprimer ]
```

### Réattribution — pas de confirmation séparée

Le choix du coureur cible **est** la confirmation : on ne valide pas un geste
dont on vient de désigner explicitement la destination. Le sélecteur affiche nom,
prénom **et date de naissance**, seule façon de départager deux homonymes.

### Correction d'identité — le conflit conserve la saisie

Sur `409`, la modale **reste ouverte**, le message nomme la fiche en conflit, et
la saisie de l'opérateur n'est pas perdue (FR-010, US1-AC3).

```text
Un coureur porte déjà cette identité (fiche #77).
```

Le message vient du serveur (`DuplicateError`), déjà en français. La modale ne le
reformule pas — elle l'affiche.

### Ressource disparue — un message, pas une trace technique

Sur `404` (un autre administrateur est passé avant), l'écran l'annonce en clair
et la page se remet à jour ; jamais de « Request failed with status 404 »
(FR-016, US2-AC5).

```text
Ce résultat n'existe plus. La page a été mise à jour.
```

### Compte rendu de réussite

Un `toast.success` par geste réussi, comme partout ailleurs dans le front.

## Mise à jour de l'écran

Après **chaque** geste réussi : `router.refresh()`.

Les cinq indicateurs de la page (épreuves, meilleure place, meilleur ratio,
top 10, format favori) et le nom en tête sont calculés **côté serveur**. Une mise
à jour d'état local ne les recalculerait pas, et FR-015 les nomme explicitement.
Aucun rechargement manuel n'est demandé à l'opérateur (SC-007).

**Une ligne en attente de validation ne bouge aucun indicateur.** Les cinq sont
calculés sur `validated` — les résultats filtrés de leur `is_pending_validation`
(`app/athletes/[id]/page.tsx:46, 81`). Supprimer une saisie en attente retire la
ligne et **rien d'autre** : c'est le comportement attendu (US2-AC6), et c'est la
disparition de la ligne, pas un compteur, qui atteste du geste. Le `toast.success`
est donc le seul retour explicite dans ce cas — ne pas le supprimer au prétexte
que la page se rafraîchit.

## Contraintes de rendu

- **La page reste rendue par `apiServer.getAthlete`** (`lib/api/server.ts:90`,
  bâti sur `serverFetch`), donc **sans cookies**. Lire la session au rendu la
  rendrait dynamique et coûterait au visiteur anonyme, ce que SC-004 interdit. La
  visibilité est décidée **dans le navigateur** ; `serverFetchAuthed` n'entre pas
  dans cette page.
- **Un seul appel de session quel que soit le nombre de lignes** : `useSession()`
  partage une clé de cache React Query ; vingt `ParticipationAdminActions` ne font
  pas vingt requêtes.
- **Composants `tcn/`**, pas `ui/` : la page est un écran public, et
  `frontend/AGENTS.md` en fait la règle. Précédent complet à suivre :
  `components/courses/CourseSourcesPanel.tsx`.
- **Mobile** : le tableau des épreuves défile horizontalement ; la sous-ligne
  d'actions reste atteignable, comme la sous-ligne de preuve aujourd'hui.

## Limite connue, hors périmètre

`tcn/Modal` gère `Escape`, le clic sur le voile et `aria-modal`, mais **n'a ni
piège à focus ni restauration du focus** à la fermeture — contrairement à
`ui/dialog`. C'est la limite des trois modales publiques existantes ; cette
feature ne l'aggrave pas et ne la corrige pas. À signaler à la revue UI/UX de fin
de branche comme dette du **composant partagé**, pas de cette page.
