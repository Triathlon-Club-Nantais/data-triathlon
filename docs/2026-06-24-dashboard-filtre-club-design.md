# Page d'accueil : afficher uniquement les résultats du TCN

Date : 2026-06-24
Cible : `frontend/`
Issue : [#6 — Filtre Club sur la page d'accueil](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/6)
Demandeur : Vincent (@Vinzzou)

> **Spec en attente de validation.** Cette PR est ouverte en *Draft* : elle ne
> contient que la spécification de la correction. L'implémentation suivra après
> validation de Vincent.

## Contexte

La page d'accueil (`/`, qui redirige vers `/dashboard`) affiche une vue
d'ensemble des participations : KPI (dossards, victoires, podiums, top 10),
répartition par type d'épreuve et épreuves préférées.

En haut à droite, un contrôle `ScopeToggle` (`components/layout/ScopeToggle.tsx`)
propose deux portées :

- **« Tous »** — tous les athlètes scrapés, club ou non (valeur par défaut) ;
- **« Membres TCN »** — uniquement les athlètes du club (`?scope=club`).

Le toggle pilote le paramètre d'URL `?scope=club`, lu par `clubFromScope()`
(`lib/scope.ts`) puis passé en filtre `club=nantais` aux appels API du
dashboard (`app/dashboard/page.tsx`, lignes 25-31).

## Problème

> « Sur la page d'accueil, il ne faut mettre que les résultats du TCN, et ne pas
> proposer de mettre tout le monde » — Vincent, issue #6.

La page d'accueil est la vitrine du club. Par défaut (sans `?scope=club`), elle
agrège **tous** les athlètes importés — y compris les ~2 500 non-membres
ramenés par les imports d'épreuve complète. Les KPI affichés (2 644 dossards,
8 victoires, etc.) ne reflètent alors pas le club mais l'ensemble du jeu de
données scrapé.

Deux conséquences :

1. **Données par défaut trompeuses** : un visiteur voit des chiffres globaux, pas
   ceux du TCN.
2. **Option non pertinente** : proposer « Tous » sur la page d'accueil n'a pas
   de sens fonctionnel pour la vitrine du club.

## Objectif

Sur la **page d'accueil uniquement**, afficher exclusivement les résultats des
membres du TCN, et retirer le choix de portée (« Tous » / « Membres TCN »).

## Design

### Changement

Dans `app/dashboard/page.tsx` :

1. **Forcer la portée club.** Ne plus dériver `club` du paramètre d'URL :
   ```diff
   - const club = clubFromScope(sp.scope);
   + const club = TCN_CLUB_FILTER; // page d'accueil = vitrine club, toujours TCN
   ```
   (import de `TCN_CLUB_FILTER` depuis `lib/club-constants`, en remplacement de
   `clubFromScope` ; `searchParams` n'est alors plus nécessaire au calcul de la
   portée.)

2. **Retirer le toggle.** Supprimer `<ScopeToggle />` (ligne 48) et son import.
   L'en-tête conserve son titre « Saison 2025 — 2026 » ; on ajuste le sous-titre
   pour expliciter la portée (ex. « Vue d'ensemble des performances **des
   athlètes du club** » — déjà le cas, on le garde).

### Hors périmètre (décision à valider)

Le `ScopeToggle` reste utilisé sur **deux autres pages** :

- `/resultats` (`app/resultats/page.tsx`) ;
- `/carte` (`app/carte/page.tsx`).

L'issue ne vise que la page d'accueil. **Proposition : on conserve le toggle sur
ces deux pages**, où comparer club vs. tous garde un intérêt (ex. situer le club
dans une épreuve, voir la carte de tous les participants).

→ **Question pour Vincent** : confirmes-tu qu'on ne touche QUE la page d'accueil,
et qu'on laisse le choix « Tous / Membres TCN » sur *Résultats* et *Carte* ? Ou
veux-tu forcer le club partout ?

### Composant `ScopeToggle`

Inchangé. Toujours utilisé par `/resultats` et `/carte`. Aucune suppression de
fichier.

## Impacts

- **Frontend uniquement.** Aucun changement backend, ni schéma, ni migration.
- **API.** Les appels du dashboard passent désormais toujours `club=nantais` ;
  comportement déjà supporté (c'est l'actuel mode « Membres TCN »).
- **URL.** `?scope=...` sur `/dashboard` devient sans effet (ignoré). Pas de
  redirection nécessaire ; on peut nettoyer le paramètre plus tard si besoin.

## Tests

- Adapter/ajouter un test rendu (`app/dashboard`) vérifiant l'absence du
  `ScopeToggle` et l'appel API avec `club=nantais`.
- `npm run build` (strict TS + RSC) et `npm test` verts.
- Vérification manuelle : page d'accueil → KPI = chiffres TCN, plus de toggle.

## Plan d'implémentation (après validation)

1. Modifier `app/dashboard/page.tsx` (portée forcée + retrait du toggle).
2. Mettre à jour/ajouter le test du dashboard.
3. `npm run lint && npm test && npm run build`.
4. Passer la PR de *Draft* à *Ready for review*, en y intégrant le changement.
