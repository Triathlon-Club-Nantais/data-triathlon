# Design — L'en-tête et les tuiles du profil athlète disent qui, et ce qui est certain

Issue [#488](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/488) —
`PROF-3` + `PROF-4` + `PROF-5` du § 7 de
`docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`. Lot de l'epic #460.

## Problème

Trois constats de l'audit, sur la même région d'écran :

- **`PROF-3`** — sur `/club`, le KPI « Podiums » compte selon `?rank=`
  (`ClubPodiumKpi.tsx`), le roster compte sur les trois portées **sans
  condition** (`club-aggregate.ts`, `buildRoster`). Les deux nombres sont justes
  et incomparables, et rien à l'écran ne le dit : basculer le `RankTypeToggle`
  fait bouger le KPI et laisse les badges du roster inchangés. Aggravant :
  `PodiumsList` tronque à 6 quand le KPI en annonce 12, sans le dire.
- **`PROF-4`** — la grille de KPI de `/athletes/[id]` est identique pour tous.
  Pour l'athlète à une seule course (164 des 350 membres, 47 %), elle rend deux
  tuiles vides, deux tautologies et une seule information.
- **`PROF-5`** — l'en-tête n'affiche que le nom et « Résultats enregistrés » :
  ni club, ni catégorie, ni genre, alors qu'`AthleteBrief` porte `gender` et
  `club`. Les homonymes existent dans ce jeu de données : arrivé sur le profil,
  on ne peut plus vérifier qu'on est sur le bon.

## Décisions d'arbitrage

**`PROF-3` — portées explicites, pas de portée unique.** L'« Attendu » de
l'issue ouvre deux voies : faire suivre `?rank=` au roster, ou faire porter à
chaque chiffre sa portée dans son libellé. On prend la seconde.

Raison technique : `ClubDashboard` est un composant serveur et `buildRoster`
tourne au rendu serveur. Faire suivre `?rank=` au roster oblige à passer la
section en composant client — le chemin qu'ont pris `ClubPodiumKpi` et
`PodiumsList` pour #132 — donc le **diff le plus long**, pas le plus court.
Raison de fond : `RosterPodiumBadges` ventile **par portée** ; sous un filtre
mono-portée il ne resterait qu'un badge, redondant avec le compte texte déjà à
côté. On écraserait une information au lieu d'en clarifier deux.

**Écarté :** aligner tout l'écran (y compris `clubSummary`) sur le toggle —
plus cohérent, mais rejuge #132 et #128, hors périmètre du lot.

**`PROF-4` — jeu de tuiles distinct sous le seuil**, plutôt que réparer les cinq
tuiles au cas par cas avec des `hint`. La réparation au cas par cas laisserait
« Top 10 : 1 » en place, qui ne dit rien quel que soit son `hint`.

**`PROF-5` — `backHref` fixe vers `/club/athletes`.** Un composant serveur ne
connaît pas l'écran d'origine. Le vrai « écran d'origine » demanderait un
`?from=` posé par tous les liens entrants (`ClubDashboard`, `ResultCard`,
`/club/athletes`, la palette ⌘K) — éparpille le lot pour un gain marginal.

## Ce qu'on construit

### 1. `PROF-3` — chaque chiffre porte sa portée

Le précédent existe déjà : `StatCardsRank` écrit « 12 · général » via le slot
`delta` de `StatCard` et `rankTypeLabel(t, { form: "long" })`. On l'imite.

- **`ClubPodiumKpi.tsx`** — ajoute `delta={rankTypeLabel(rankType, { form: "long" })}`.
  Rend « général », « catégorie », « genre », « général, genre ou catégorie ».
  Aucune microcopie nouvelle : `lib/labels.ts` porte déjà les quatre formes.
- **`ClubDashboard.tsx`** — une ligne sous le `h2` de la section roster :
  « podiums toutes portées confondues ». C'est la phrase qui manque ; aucun
  chiffre ne change.
- **`PodiumsList.tsx`** — état local d'extension. `slice(0, APERCU_PODIUMS)`
  tant qu'il n'est pas étendu, liste entière sinon. Bouton « Voir les N autres
  podiums » rendu sous la liste seulement si `podiums.length > APERCU_PODIUMS`.
  Extension **totale**, sans plafond : le tri rang-asc met le meilleur en haut,
  et qui clique demande la liste.

`club-aggregate.ts` n'est pas touché.

**Accessibilité** — l'`AnnonceStatut` déjà en place reflète `podiums.length` ;
l'extension déclenche donc l'annonce WCAG 4.1.3 sans code supplémentaire.

### 2. `PROF-4` — sous 3 épreuves, ce qui est certain

Contrainte du composant : `StatCard` rend `value` en 68 px display **sans
clamp** (`.tcn-stat-value` ne fait que du trim de boîte de texte). Un nom
d'épreuve y déborde. Le nom va donc en `hint`, `value` reste court.

Trois régimes, sur le décompte des participations **validées**
(`!is_pending_validation`, comme les KPI actuels depuis #438) :

- **0 épreuve validée** — pas de grille. Un bloc « Aucune épreuve enregistrée
  pour l'instant. » suivi de l'appel à l'action « Ajouter une épreuve → »
  (`/ajouter`, cohérent avec l'`EmptyState` de `/club`). Si `pendingCount > 0`,
  le bloc le mentionne.
- **1 ou 2 épreuves** — trois tuiles au plus, tirées de la **dernière
  participation validée** (par `course.event_date`) :
  - `Épreuves` = décompte, `hint` = « N en attente de validation » si besoin
    (comportement actuel conservé).
  - `Discipline` = `formatToken(event_type, distance_km)`, `hint` = nom de
    l'épreuve.
  - `Temps` = `total_time`, `hint` = date formatée. Si `total_time` est absent,
    cette tuile devient `Place` = `rank_overall`, `hint` = « Ne sur M ». Si les
    deux manquent, la tuile n'est **pas rendue** — jamais de « — » nu.
  - Sous la grille, « Ajouter une épreuve → ».
- **3 épreuves ou plus** — les cinq tuiles actuelles, inchangées.

Le seuil est une constante nommée (`SEUIL_TUILES_COMPLETES = 3`).

**Isolation** — la logique de choix (quel régime, quelles tuiles, avec quelles
valeurs) sort de `page.tsx` vers une fonction pure `lib/utils/athlete-stats.ts`.
La page ne fait que rendre ce qu'elle reçoit. C'est ce qui rend le lot testable
sans monter un rendu pour chaque combinaison.

### 3. `PROF-5` — l'en-tête sur `PageHeader`

`app/(public_restricted)/athletes/[id]/page.tsx` remplace son bloc en styles
inline par un flex à deux enfants : `AthleteAvatar`, puis `PageHeader`.

L'avatar reste **frère** de `PageHeader` plutôt que d'ajouter une prop `media`
au composant partagé pour un unique appelant.

| Prop | Contenu |
| --- | --- |
| `backHref` / `backLabel` | `/club/athletes` / « Athlètes du club » |
| `eyebrow` | `athlete.club`, repli sur « Résultats enregistrés » si `null` |
| `title` | Nom complet — le `h1` vient de `PageHeader` |
| `children` | `MetaPill` catégorie + `MetaPill` `genderShort(athlete.gender)` |
| `actions` | `AthleteSelection` + `AthleteAdminPanel` |

La **catégorie** n'est pas sur `AthleteBrief` : elle vit sur la participation
(`p.category`) et change avec l'âge. On prend celle de la dernière participation
validée, avec l'année de cette participation en `title` de la pastille pour dire
qu'elle date. Chaque pastille est omise si sa donnée manque.

Le slot `actions` remplace le `marginLeft: "auto"` inline actuel.

## Tests

TDD, dans l'ordre d'écriture :

- **`lib/utils/athlete-stats.test.ts`** (nouveau) — le cœur. 0 épreuve,
  1 épreuve avec temps, 1 épreuve sans temps mais avec rang, 1 épreuve sans
  temps ni rang, 2 épreuves (la plus récente gagne), 3 épreuves (régime
  complet), participations en attente exclues du décompte.
- **`ClubPodiumKpi.test.tsx`** — le `delta` rendu pour chacun des quatre modes.
- **`PodiumsList.test.tsx`** — bouton absent à 6 podiums ou moins ; présent avec
  le bon décompte au-delà ; clic ⇒ liste entière ; l'annonce suit.
- **`page.test.tsx`** (profil athlète) — en-tête : club en eyebrow, repli sans
  club, pastilles présentes/omises, lien de retour ; tuiles : les trois régimes,
  et l'absence de tout « — » sous le seuil.
- **`ClubDashboard.test.tsx`** — la mention « toutes portées » sur la section
  roster.

`club-aggregate.test.ts` reste inchangé — le module ne bouge pas.

## Contraintes en vigueur

Les deux contraintes de #325 : identité arbitrée (`--tcn-*`, Anton/Barlow) et
frontière `components/tcn/` vs `components/ui/` non rejugée. Cycle
`docs/WORKFLOW-IA.md` : voie Superpowers, TDD, `requesting-code-review`, puis le
sous-agent `ui-ux-review` en fin de branche.

## Hors périmètre

- Le volet « aucun titre sur la page » de `PROF-5` : traité par `A11Y-1`/`A11Y-2`
  (#475), qui a posé `PageHeader`. Déjà fait, c'est la dépendance qu'on consomme.
- Aligner `clubSummary` ou le roster sur `?rank=` (option écartée ci-dessus).
- Un écran `/club/podiums` dédié.
- Le `?from=` de provenance sur les liens vers un profil.
