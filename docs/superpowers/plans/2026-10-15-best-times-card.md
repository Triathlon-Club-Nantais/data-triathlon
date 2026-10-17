# Carte « Meilleurs temps » sur la fiche athlète (#1361)

**Goal:** une carte « Meilleurs temps » sur `/athletes/[id]`, une ligne par
couple (discipline, format), avec le meilleur temps et un lien vers la
participation. Calcul côté client à partir de `getAthlete`, aucune API touchée.

**Brainstorming (options retenues, tranchées sans aller-retour) :**

- Clé de regroupement : `disciplineOf(event_type)` + `formatToken(...)`, car
  `formatToken` rend « M » pour un triathlon comme pour un duathlon.
- Exclusions, mêmes règles que les tuiles (#438, #894, #115) : en attente de
  validation, relais (`estRelais`), `is_reliable === false`. S'y ajoutent les
  cas où aucun temps comparable n'existe : temps absent ou illisible
  (`secondsFromHms`), non-finisher (DNF/DNS/DSQ), discipline vide, et tout
  format qui n'est ni une taille (XS à XL) ni une distance en km : les replis
  de `formatToken` (« CAP », « TR », « CYC », « — ») mêleraient un 5 km et un
  marathon (relevé en revue).
- À temps égal, l'épreuve la plus ancienne (`event_date`) garde la ligne,
  quel que soit l'ordre reçu.
- Ordre : par libellé de discipline, puis temps croissant (les formats courts
  d'abord sans table d'ordre à maintenir).
- Rendu : `Card` à titre `<h2>` (motif de `VolunteerActionsList`), une `LigneCarte` par ligne (lien vers
  `/courses/{id}/participations/{id}`, `FormatChip` en marqueur, temps en
  valeur) : même dessin que les cartes d'épreuves, tient à 360 px.
- État vide : la carte ne se rend pas (comme Progression et Répartition).
  Elle ne se rend qu'en régime `complet` (3 épreuves validées et plus) : en
  dessous, la tuile « Temps » montre déjà le même temps (relevé en revue UI).
- Libellé « meilleur temps sur M » dans le nom accessible de chaque ligne,
  jamais « record » ; une phrase rappelle que deux parcours d'un même format
  diffèrent.
- Placement : juste après les tuiles, avant Progression.

## Task 1: calcul pur `bestTimes` (TDD)

`frontend/lib/utils/best-times.ts` + `best-times.test.ts` : un test par
exclusion, le regroupement discipline × format, le choix du minimum, l'ordre.

## Task 2: composant `BestTimesCard` (TDD)

`frontend/components/athletes/BestTimesCard.tsx` + test RTL : rien sans ligne,
une ligne, plusieurs lignes, lien et libellé.

## Task 3: branchement sur la page

`app/(public_restricted)/athletes/[id]/page.tsx`, puis `npm test`,
`npm run lint`, `npm run build`.
