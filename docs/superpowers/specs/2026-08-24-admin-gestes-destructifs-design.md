# Une seule grammaire pour les gestes destructifs de l'admin

**Date** : 2026-08-24 · **Issue** : #499 (`ADM-7` + `ADM-8` + `ADM-9`) · **Epic** : #460
· **Preuves** : `docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`, § 9

## Le problème

Le back-office s'adresse à un bénévole occasionnel, non formé, qui revient après
plusieurs mois. Rien à l'écran ne lui dit de façon constante « ce bouton
détruit ». Quatre mécanismes de confirmation coexistent pour un même verbe, et
la couleur ne suit aucune règle — le geste le plus grave est parfois le moins
signalé.

| Geste | Signalement | Confirmation | Gravité réelle |
| --- | --- | --- | --- |
| Purger tous les résultats / toutes les épreuves | `destructive` | `Dialog` maison, chiffré, mot à taper | sans retour |
| Retirer une adresse autorisée (`AllowedEmailsTable.tsx:85`) | `outline` | `window.confirm` | ferme un accès, coupe les sessions vivantes |
| Fermer les sessions (même ligne, même taille) | `outline` | aucune | réparable par une reconnexion |
| Supprimer un groupe (`GroupsTable.tsx:170`) | `outline` | aucune | sans retour |
| Supprimer un rôle (`RolePermissionsEditor.tsx:203`, `:215`) | — | `window.confirm` ×2 | sans retour |
| Retirer un rôle (`UserRolesTable.tsx:47`) | ghost | **aucune, premier clic** | ôte des pouvoirs, possiblement les siens |
| Supprimer une épreuve | `destructive` | `Dialog` maison, chiffré | sans retour |

Deux défauts s'ajoutent à cette hétérogénéité :

- **Le voisinage** (`ADM-7`) : « Purger tous les résultats » et « Supprimer
  toutes les épreuves » vivent en pied de `/admin/courses`
  (`app/admin/courses/page.tsx:43-44`), l'écran où l'on vient corriger la date
  d'une épreuve. Trois `Card` dans le même `space-y-6` : qui feuillette le
  catalogue jusqu'à la dernière page et fait défiler se retrouve à un clic de la
  destruction de toute la base. Les deux cartes sont bien faites
  individuellement — le problème n'est pas la confirmation, c'est le voisinage.
- **Le silence sur les refus** : `GroupsTable` et `UserRolesTable` laissent
  cliquer un geste que le serveur refusera, et ne le disent qu'après.

Traiter ces trois entrées séparément ajouterait trois grammaires de plus. Le
public occasionnel n'acquiert un réflexe que si le code couleur vaut partout.

## La règle

Une phrase, écrite une fois dans `frontend/AGENTS.md`, appliquée aux cinq
écrans :

> `variant="destructive"` **et** confirmation dès qu'un geste ferme un accès ou
> détruit une donnée. Neutre et sans confirmation pour tout ce qui se refait.

Une seule exception, nommée dans le code là où elle s'applique : la croix de
retrait de rôle reste `ghost` au repos et vire `destructive` au `hover` et au
`focus-visible`. Motif : une croix par badge, plusieurs badges par ligne — en
rouge permanent, `/admin/utilisateurs` devient un champ de croix rouges où plus
rien ne ressort. Le rouge apparaît au moment où l'on vise, ce qui est le moment
utile. C'est le raisonnement du commentaire de `CoursesAdminTable.tsx:253-264`,
appliqué à une densité inverse.

Conséquence directe de la règle, à noter parce qu'elle surprend : « Fermer les
sessions » **ne change pas**. Le geste se répare par une reconnexion, donc il
reste neutre et sans confirmation. Son contraste avec « Retirer » ne vient plus
de sa propre apparence mais du rouge de son voisin — ce qui est exactement ce
que `ADM-8` réclame.

## Le mécanisme unique

Un seul composant, `components/admin/DangerConfirm.tsx`, exposant deux
ergonomies d'appel pour un seul rendu.

**Où il vit.** Dans `components/admin/`, ni `components/ui/` ni
`components/tcn/` : les appelants sont tous sous `/admin`, ce qui laisse
intacte la frontière gelée par #460. Le jour où un geste destructif apparaît
côté public, il sera temps de le remonter — pas avant.

**Ce qu'il est.** Le `Dialog` du produit, jamais le `confirm` du navigateur :
ce dernier n'est ni traduisible, ni stylable, ni testable au même titre.

### Forme déclarative — les gestes chiffrés

Pour les trois gestes qui annoncent leur ampleur avant d'agir, le corps du
dialog est fourni en `children` et l'action reste bloquée tant que le chiffrage
n'est pas arrivé :

```tsx
<DangerConfirm
  open={ouvert}
  onOpenChange={fermer}
  titre="Supprimer toutes les épreuves ?"
  description="Cette action est irréversible…"
  motDeConfirmation="SUPPRIMER"
  actionBloquee={!impact.data}
  libelleAction="Supprimer définitivement"
  enAttente={purge.isPending}
  onConfirm={confirmer}
>
  {/* liste chiffrée, squelette de chargement, message d'échec du chiffrage */}
</DangerConfirm>
```

`motDeConfirmation` reste facultatif : seules les deux purges l'exigent
aujourd'hui, et le composant ne l'impose pas aux autres.

### Forme impérative — les gestes simples

Pour les quatre gestes sans chiffrage, un hook remplace `window.confirm` un pour
un, sans qu'un tableau ait à porter un `useState` d'ouverture et la ligne en
cours :

```tsx
const confirmer = useDangerConfirm();

async function supprimer(acces: AllowedEmail) {
  if (
    !(await confirmer({
      titre: `Retirer « ${acces.email} » ?`,
      description: "Ses sessions ouvertes seront fermées immédiatement.",
      libelleAction: "Retirer",
    }))
  ) {
    return;
  }
  // …
}
```

Le provider qui porte le dialog partagé est monté dans `app/admin/layout.tsx` —
portée admin, pas globale, pour la même raison qui garde le composant dans
`components/admin/`.

## L'écran de maintenance

Les deux purges quittent `/admin/courses` pour une route à elles :
`app/admin/maintenance/page.tsx`, un `PageHeader` suivi d'une section nommée
« Zone de dangers — gestes sans retour » portant les deux cartes déplacées sans
changement de comportement. `/admin/courses` se termine désormais sur son
tableau.

L'écran plutôt que la section repliée sur place : replier ne supprime pas le
voisinage, il le cache. Une route séparée retire les deux gestes du chemin de
qui vient corriger une date, ce qui est le défaut que `ADM-7` décrit.

**Un accroc à traiter au passage.** `nav.config.ts:50` ne porte qu'un code de
pouvoir, or cet écran doit s'annoncer à qui détient `courses:wipe_all` **ou**
`participations:wipe_all` — deux pouvoirs distincts et attribuables séparément
(`backend/app/core/permissions.py:161` et `:214`). Choisir l'un des deux
proposerait l'écran à qui n'y peut rien faire, ce que le fichier se reproche
déjà nommément en commentaire (`ADM-6`). Le type devient
`permission?: string | string[]`, et le test de `:306` un `.some()` — deux
lignes, et la règle reste lisible.

Les deux cartes gardent leur propre garde par pouvoir : elles se masquent déjà
seules, et la navigation n'est pas une garde.

## Les huit points d'appel

| Écran / composant | Aujourd'hui | Après |
| --- | --- | --- |
| `AllowedEmailsTable` « Retirer » | `outline` + `window.confirm` | `destructive` + `confirmer()` nominatif |
| `AllowedEmailsTable` « Fermer les sessions » | `outline`, aucune confirmation | **inchangé** — le geste se refait |
| `GroupsTable` « Supprimer » | `outline`, aucune confirmation | `destructive` + `confirmer()` nominatif ; refus annoncé avant le clic (ci-dessous) |
| `RolePermissionsEditor` « Supprimer le rôle » (`:215`) | `window.confirm` | `destructive` + `confirmer()` |
| `RolePermissionsEditor` bascule superutilisateur (`:203`) | `window.confirm` | `confirmer()`, couleur **neutre** (voir ci-dessous) |
| `UserRolesTable` croix de retrait | ghost, aucune confirmation | `confirmer()` nominatif + rouge au survol et au focus |
| `DeleteCourseDialog` | `Dialog` maison chiffré | réécrit sur `DangerConfirm`, comportement identique |
| `WipeCoursesCard`, `WipeParticipationsCard` | `Dialog` maison chiffré | réécrites sur `DangerConfirm`, déplacées vers `/admin/maintenance` |

### Le seul geste que la règle laisse neutre tout en le confirmant

La bascule du statut de superutilisateur (`RolePermissionsEditor.tsx:200-212`)
va dans les deux sens : le poser accorde tout pouvoir, le retirer en ôte. Ni
l'un ni l'autre ne ferme un accès ni ne détruit une donnée, donc la couleur
reste neutre ; mais les deux sens méritent d'être confirmés, et ils le sont
déjà. Le changement se borne ici au mécanisme — `confirmer()` au lieu de
`window.confirm` — sans que le lot invente une troisième catégorie de gravité
pour ce seul bouton.

### Dire le refus avant le clic

`GroupsTable` : quand `groupe.member_count > 0`, le bouton « Supprimer » est
désactivé et porte une infobulle « Videz d'abord le groupe (N membres) ». Le
déclencheur de l'infobulle porte sur un `<span tabIndex={0}>` enveloppant, et
non sur le bouton : un bouton désactivé ne reçoit ni survol ni focus
(`buttonVariants` pose `disabled:pointer-events-none`), son infobulle ne
s'ouvrirait jamais.
L'API refuse déjà ce cas par un 409 ; l'écran cesse de laisser cliquer pour le
découvrir. La cible de la règle est le commentaire de `GroupsTable.tsx:68-70`,
qui justifiait l'absence de confirmation par ce refus serveur : le refus étant
désormais annoncé, l'argument tombe et la confirmation redevient due — le geste
détruit bien un groupe.

## Le cas « votre dernier rôle », et son rétrécissement assumé

L'issue demande d'annoncer avant le clic le retrait de son propre dernier rôle,
« que le serveur refuse par un conflit ». Le serveur ne refuse pas ce
prédicat-là : `backend/app/api/v1/admin_roles.py:182` refuse que
**l'organisation perde son dernier administrateur actif**. Les deux énoncés ne
coïncident pas, et recalculer le second côté front dupliquerait une règle métier
serveur qui divergerait au premier changement.

Le dialog annonce donc ce que le front sait avec certitude, en comparant
`session.id` à l'utilisateur visé :

> **Ce rôle est le vôtre.** Vous pourriez perdre l'accès à cet écran.

Le cas « dernier administrateur du club » reste porté par le message du 409, que
le front rend déjà tel quel — il est écrit en français côté serveur, et
`UserRolesTable.tsx:52-55` documente ce choix.

## Tests

TDD, Vitest. Deux tests neufs pour le mécanisme, les autres réécrits sur les
appelants existants :

- `DangerConfirm` : le mot à taper active l'action et pas avant ; `actionBloquee`
  la maintient inerte ; « Renoncer » ferme sans agir ; le titre et le libellé
  d'action sont ceux passés.
- `useDangerConfirm` : la promesse résout `true` sur confirmation, `false` sur
  renoncement et sur fermeture du dialog.
- Les trois suites qui simulent `window.confirm`
  (`RolePermissionsEditor.test.tsx:465`, `AllowedEmailsTable.test.tsx`) passent
  sur le dialog ; le mock disparaît.
- `UserRolesTable` : la croix n'agit qu'après confirmation ; l'avertissement
  « ce rôle est le vôtre » apparaît pour sa propre ligne et pas pour une autre.
- `GroupsTable` : bouton désactivé et infobulle quand `member_count > 0` ;
  confirmation exigée sinon.
- `/admin/maintenance` : l'écran est gardé, et l'entrée de navigation apparaît
  pour chacun des deux pouvoirs pris isolément (le OU de `nav.config`).

Le cycle de fin de branche reste celui de `docs/WORKFLOW-IA.md` :
`requesting-code-review`, puis le sous-agent `ui-ux-review` — la branche touche
`frontend/` —, puis `verification-before-completion` et
`finishing-a-development-branch`.

## Hors périmètre

- La cible de 16 px de la croix de retrait appartient au lot `CIBLE-1`.
- L'identité visuelle arbitrée (`--tcn-*`, Anton/Barlow) et la frontière
  `components/tcn/` vs `components/ui/` ne sont pas rejugées (#325, #460).
- Les autres entrées du § 9 de l'audit (`ADM-1` à `ADM-6`) ont leurs propres
  lots.
