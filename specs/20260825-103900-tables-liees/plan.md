# Implementation Plan: Des tableaux qui se lisent, des lignes qui se partagent

**Branch**: `worktree-issue-481-tables-liees` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260825-103900-tables-liees/spec.md` — issue #481, lot de l'epic #460, refs #325.

## Summary

Six listes de données des écrans publics sont des grilles de `<div>` dont
l'en-tête n'est reliée à rien : un lecteur d'écran énonce les valeurs sans
jamais nommer leurs colonnes. Sur l'une d'elles — le classement d'une épreuve —
la ligne est en outre un `role="button"` piloté par navigation programmatique,
si bien qu'on ne peut ni ouvrir un résultat dans un nouvel onglet, ni copier son
lien.

L'approche retenue tient en trois décisions, prises en Phase 0 :

1. **Balises de tableau réelles, géométrie `display: grid` conservée, rôles
   ARIA redéclarés.** La géométrie ne se réexprime pas en disposition de tableau
   sans dérive (pistes souples, `column-gap`), et surcharger `display` sur un
   `<table>` peut lui retirer sa sémantique : les rôles la redonnent. Détail et
   alternatives rejetées : `research.md` D1.
2. **La ligne n'est plus l'ancre.** Un rôle ARIA remplace le rôle implicite :
   un `<a role="row">` cesserait d'être annoncé comme un lien, ce qui
   contredirait FR-002. L'ancre descend donc dans la cellule du nom et couvre la
   ligne par un pseudo-élément, mécanisme mutualisé dans la classe
   `.tcn-rowlink` **existante**. Un seul arrêt clavier par ligne (FR-011).
   Détail : `research.md` D2.
3. **L'attente vient de `useLinkStatus()`**, vérifié présent dans Next 16.3.1,
   avec le `prefetch={false}` sans lequel elle serait sautée en production — le
   dépôt a déjà tranché ainsi ailleurs pour la même raison (#425). Détail :
   `research.md` D3.

**Ce que la lecture du code a changé par rapport à l'issue** : ses repères sont
antérieurs à #509, #489 et à la refonte du tableau de bord. Cinq listes sur six
ont **déjà** une ligne cliquable correcte — le travail y est de déplacer l'ancre,
pas de la créer — et les cibles tactiles des en-têtes triables sont **déjà
livrées** par #479. L'inventaire revérifié est dans `data-model.md` § 1.

## Technical Context

**Language/Version** : TypeScript strict, React 19, Next.js **16.3.1** (App Router)

**Primary Dependencies** : `next/link` (dont `useLinkStatus`), Tailwind CSS v4, `@base-ui/react` (non concerné ici) — aucune dépendance ajoutée

**Storage** : N/A — la feature ne touche ni la base, ni les DTO, ni l'API

**Testing** : Vitest + React Testing Library, deux projets (`node` par défaut, `jsdom` pour les `**/*.test.tsx`, #508). Les six listes ont déjà leur fichier `*.test.tsx`, donc **aucun changement de `vitest.config.ts`**.

**Target Platform** : navigateurs modernes (`:has()` est déjà employé dans `app/globals.css:496`, verrouillé par `components/club/AthleteSortToggle.test.tsx:34`)

**Project Type** : application web — **front uniquement** sur cette feature

**Performance Goals** : sur une réponse qui prend jusqu'à 1,43 s, la ligne activée porte un état d'attente visible dès le relâchement du clic, observable à l'œil nu (SC-004). Le `prefetch={false}` des lignes du classement **retire** par ailleurs jusqu'à 20 préchargements de routes dynamiques par page.

**Constraints** : apparence rendue strictement inchangée (FR-007, SC-005) ; un seul arrêt clavier par ligne (FR-011) ; identité `--tcn-*` et frontière `tcn/` vs `ui/` non rejugées (#325, cf. #460) ; largeurs plancher et repli mobile hors périmètre (#461)

**Scale/Scope** : 6 listes, 6 fichiers de rendu, 6 fichiers de test existants à reprendre, 1 bloc CSS partagé à étendre. Aucun fichier backend.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Aucun libellé utilisateur n'est ajouté ni modifié — la feature est structurelle. Les identifiants neufs restent techniques et anglais (`useLinkStatus`, `aria-sort`, `colSpan`) ; les noms de test et les commentaires de règle suivent l'usage du dossier, où le français porte le métier (`EnteteTriable`, `lignes`, `perimetreTri`) et l'anglais la technique. |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Aucun fichier backend n'est touché : ni router, ni service, ni repository, ni modèle. |
| III | TDD sans réseau (non-négociable) | ✅ | Un test rouge **par liste** avant sa conversion, et un test rouge pour la ligne-lien du classement avant de la convertir. Aucun réseau : jsdom rend les six listes à partir de données fournies. La limite de jsdom sur le nom accessible d'une cellule est nommée (`research.md` D7) et compensée par la vérification manuelle de `quickstart.md` § 3.1. |
| IV | Contrats API et CLI stables | ✅ | Aucun appel, aucun champ, aucun paramètre. Toutes les données affichées sont déjà servies, y compris l'identifiant de participation dont l'adresse de détail est construite. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse n'est lu ni ajouté. `scope` et `q` du classement restent inchangés. |
| VI | Simplicité / YAGNI | ✅ | Aucun composant partagé, aucune abstraction — le seul composant neuf est local et non exporté (cf. §Structure Decision) : le mécanisme de ligne activable **étend la classe `.tcn-rowlink` qui existe déjà** et porte déjà survol, fond et anneau de focus. Six emplois du même mécanisme CSS ne sont pas une abstraction spéculative. `components/ui/table.tsx` est écarté avec sa raison (`research.md` D1). |

**Re-check après Phase 1** : les six lignes tiennent. La conception n'a introduit
ni composant, ni dépendance, ni fichier de configuration ; le seul ajout partagé
est un bloc CSS dans `app/globals.css`, à côté de celui qu'il prolonge.

**Complexity Tracking** : sans objet — aucune violation à justifier.

## Project Structure

### Documentation (this feature)

```text
specs/20260825-103900-tables-liees/
├── spec.md                            # /speckit-specify
├── plan.md                            # ce fichier
├── research.md                        # Phase 0 — D1 à D7
├── data-model.md                      # Phase 1 — inventaire et forme des tableaux
├── quickstart.md                      # Phase 1 — vérification de bout en bout
├── contracts/
│   └── structure-accessible.md        # Phase 1 — C1 à C7, le contrat en rôles
├── checklists/
│   └── requirements.md                # qualité de la spec
└── tasks.md                           # /speckit-tasks — PAS créé ici
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── globals.css                                     # `.tcn-rowlink` étendue (bloc partagé)
│   └── (public_restricted)/
│       ├── ajouter/page.tsx           (+ page.test.tsx)         # tableau 4
│       ├── athletes/[id]/EventsTable.tsx (+ .test.tsx)          # tableau 3 — sous-ligne
│       └── courses/[id]/page.tsx      (+ page.test.tsx)         # tableau 6 — lignes inertes
└── components/
    ├── dashboard/RecentCourses.tsx    (+ .test.tsx)             # tableau 5
    └── results/
        ├── EventList.tsx              (+ .test.tsx)             # tableau 2 — deux natures de ligne
        └── RaceFinishers.tsx          (+ .test.tsx)             # tableau 1 — lien, attente, aria-sort
```

**Structure Decision** : aucune arborescence nouvelle. Chaque tableau est
converti **dans le fichier où il vit**, et le seul point partagé est
`app/globals.css` — là où `.tcn-rowlink` est déjà définie
(`globals.css:432-449`), dans la couche `base` que le commentaire du fichier
justifie longuement. Aucun composant **partagé ni exporté** n'est créé : la
frontière `tcn/` vs `ui/` n'a donc pas à être arbitrée, et #325 reste fermée.
Le seul composant neuf est **local à `RaceFinishers.tsx`** et non exporté —
l'enfant du `<Link>` qui lit `useLinkStatus`, que Next impose de lire depuis un
descendant du lien (`research.md` D3). Il ne monte pas dans `components/`.

## Ordre d'exécution recommandé

Le lot est un **L**, mais il se découpe en tranches indépendantes et
livrables une à une. L'ordre ci-dessous fait remonter le risque d'abord.

1. **`RaceFinishers` (tableau 1) en premier**, et seul dans sa tranche. Il porte
   les trois nouveautés — la ligne-lien (FR-002/003/004), l'attente (FR-005) et
   `aria-sort` (FR-006) — en plus de la conversion. C'est aussi la liste dont la
   géométrie est la plus mouvante (colonnes d'inters variables). Ce qui s'y
   révèle vaut pour les cinq autres.
2. **Le bloc `.tcn-rowlink` se fige à l'issue de la tranche 1**, une fois le
   mécanisme éprouvé sur le cas le plus dur. Les cinq listes suivantes le
   consomment sans le rouvrir.
3. **Les listes simples** (4 `ajouter`, 5 `RecentCourses`, 6 « Top clubs ») —
   trois conversions sans piège, la sixième sans ligne activable du tout.
4. **Les deux listes à structure composée**, en dernier : `EventsTable`
   (tableau 3, `<tbody>` par entrée pour la sous-ligne — `research.md` D4) puis
   `EventList` (tableau 2, ligne-dépliante et lignes révélées — D5).

Chaque tranche : test rouge → conversion → test vert → vérification visuelle de
l'écran (`quickstart.md` § 3.4). Le § 3.1 (lecteur d'écran) se passe une fois,
sur les six, à la fin.

## Risques identifiés, et ce qui les couvre

| Risque | Couverture |
| --- | --- |
| La sémantique de tableau tombe quand même dans un navigateur donné | Rôles ARIA redéclarés (D1) **et** vérification manuelle au lecteur d'écran (`quickstart.md` § 3.1), qui est le seul juge |
| Une dérive visuelle passe inaperçue | `gridTemplateColumns`, gouttières et paddings **littéralement recopiés** ; FR-007/SC-005 ; relecture écran par écran (§ 3.4) ; `ui-ux-review` en fin de branche |
| Un `href` par cellule ferait passer C3 en cassant FR-011 | Assertion explicite « un seul élément focalisable par ligne » (contrat C3) |
| L'attente ne s'allume jamais en production | `prefetch={false}` sur les lignes du classement, et la raison écrite dans le code (D3) |
| Le trait de séparation d'`EventsTable` se déplace | Il passe sur le `<tbody>`, pas sur les `<tr>` — l'invariant de #270 (pas de trait pour une ligne en attente sans sous-ligne) est nommé dans C7 |
| La ligne de groupe d'`EventList` devient un lien par mimétisme | D5 le dit explicitement : elle déplie, elle reste un `<button aria-expanded>` |

## Ce que ce plan ne fait pas

- **Le repli mobile et les largeurs plancher** (1 080 px, 988 px, 966 px,
  480 px) — lot #461 (`RESP-1`). Ce lot doit lui laisser une base **inchangée**.
- **Les cibles tactiles des en-têtes triables** — déjà livrées par #479.
- **Les tableaux du back-office**, qui sont déjà de vrais tableaux.
- **Toute retouche d'identité visuelle** ou de la frontière `tcn/` vs `ui/`
  (#325, cf. #460).
