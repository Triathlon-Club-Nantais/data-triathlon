# Accueil carrefour : design

Date : 2026-10-17. Voie Superpowers. Source : brainstorming du 16-17/10/2026
après la livraison de la navigation en trois espaces
(`2026-10-10-navigation-espaces-design.md`, #1336, #1299).

## Constat

#1299 a retiré de `/dashboard` les blocs collectifs en double avec `/club`
(compteurs, performance du club, types d'épreuves) sans rien mettre à la place.
Sur la preview, en début de saison, la page se réduit à « Ma saison » vide,
trois épreuves et une carte « Le club » qui n'est qu'un lien.

Objectif : un accueil qui produit un effet « whaoo » pour les adhérents comme
pour une vitrine du club, sans recréer le doublon avec `/club`, et qui
préfigure l'espace personnel (epic #1360).

## Décisions de cadrage

- **Trois pages, trois rôles** :
  - `/` **Accueil** : le pouls du club maintenant, et le carrefour vers les
    espaces. Aucun détail chiffré par type de rang, aucun tableau.
  - `/club` **Club** : la référence collective détaillée. **Inchangée.**
  - `/mon-espace` **Mon espace** : le personnel (contenu actuel de
    `/dashboard`).
- **Multi-club : prêt, pas fait.** L'accueil lit l'identité du club courant
  à un seul endroit (`CLUB_NAME` et constantes voisines). Ni sélecteur de club,
  ni club dans l'URL, ni données multi-club dans ce chantier.
- **Mise en page retenue** : un bandeau « direct » orange, puis une grille de
  tuiles d'espaces sobres (option A du brainstorming, préférée au « bento »).
- **Pas de bandeau défilant ni de « record club battu »** en v1 : ils
  demandent un calcul backend nouveau (historique des records).

## Pages et navigation

### `/` : Accueil

Rendu côté serveur dans `app/(public_restricted)/`, donc sous la garde du mot
de passe du site. La redirection `/` → `/dashboard` de `next.config.ts`
disparaît.

**Bandeau « direct »** (fond `--tcn-orange-grad`, texte blanc) :

- en-tête : nom du club et saison en cours (« Triathlon Club Nantais ·
  2026-2027 ») ;
- à gauche, la **dernière sortie** du club :
  - titre « Ce week-end » si la fin de la sortie date de moins de 7 jours,
    sinon « Dernière sortie · 6 sept. » ;
  - chiffre géant (Anton) : les TCN au départ (« 48 TCN ») ;
  - en dessous : épreuves et podiums de la sortie ;
- sous la sortie, les **chiffres de la saison en cours** : résultats, athlètes,
  podiums ;
- à droite, un **histogramme des résultats par mois** de la saison en cours
  (`stats.by_month`), avec un résumé textuel pour les lecteurs d'écran ;
- les chiffres s'animent (montée de 0 à la valeur) au premier affichage, sauf
  sous `prefers-reduced-motion: reduce`, où ils s'affichent directement. La
  valeur finale est dans le HTML serveur : l'animation est un pur décor.
- sans sortie (aucune course TCN validée cette saison, ou appel en échec) : le
  bloc de gauche dit « Pas encore de course cette saison » ; les chiffres de la
  saison et l'histogramme restent.

**Tuiles d'espaces** (cartes `tcn/Card`, une ligne d'info chacune, toute la
tuile est le lien, cible tactile de 44 px au moins) :

| Tuile | Visible pour | Ligne d'info | Source |
| --- | --- | --- | --- |
| Résultats | tous | dernière épreuve importée et sa date | `listEvents({ page_size: 1 })`, serveur |
| Club | tous | podiums de la saison | `stats.rank_counters.all.podiums`, serveur |
| Mon espace | tous | mes épreuves de la saison, sinon « Choisissez votre nom » | athlète retenu (`useSelectedAthlete`), client |
| Encadrement | `can_supervise` | aucune en v1 (simple lien) | session, client |
| Back-office | `can_administer` | badge du total « à traiter » | `useNavBadges`, client |

Les tuiles qui dépendent de la session ou du navigateur se montent côté client,
comme le rail : la page serveur ne lit aucune session et reste en cache. Leur
emplacement est réservé sans rien affirmer pendant la lecture de la session
(règle #954).

### `/mon-espace` : Mon espace

L'actuel `app/(public_restricted)/dashboard/page.tsx` déplacé sous
`app/(public_restricted)/mon-espace/`, titre « Mon espace ». Contenu inchangé
(Ma saison, invitation à choisir son nom, dernières épreuves, sélecteurs de
saison et de disciplines), **moins la carte « Le club »**, puisque l'accueil y
mène.

`/dashboard` est supprimé sans redirection (pas de compatibilité ascendante).
Toutes les références internes à `/dashboard` (navigation, `not-found`,
`NoAdminAccess`, `SeasonEmptyState`, tests, docs) passent à `/` ou à
`/mon-espace` selon le sens : « retour à l'accueil » vers `/`, « ma saison »
vers `/mon-espace`.

### Navigation (`components/layout/nav.config.ts`)

- L'entrée « Tableau de bord » (`/dashboard`) devient « Accueil » (`/`).
- Une entrée « Mon espace » (`/mon-espace`) s'ajoute dans l'espace Résultats.
- Barre basse mobile de l'espace Résultats : Accueil, Résultats, Club,
  Rechercher (inchangée, Accueil pointe désormais vers `/`). Mon espace reste
  joignable par le rail, le tiroir et sa tuile.
- `home` de l'espace public passe à `/`.

## Données

### Nouvel endpoint : `GET /api/v1/club/last-outing`

Paramètre : `federal_only` (même sens que sur `/stats`). Réponse :

```json
{ "end_date": "2026-09-06", "events": 3, "athletes": 48, "podiums": 9 }
```

ou `null` quand la saison en cours n'a aucune course TCN validée.

`end_date` est la date de la dernière course ; la fenêtre n'est pas renvoyée (un samedi seul ferait mentir une date de début).

- **Sortie** : soit `d` la date d'épreuve la plus récente portant au moins une
  participation TCN validée, dans la saison en cours. La fenêtre est
  `[d − 1 jour, d]` : un samedi et un dimanche forment une seule sortie.
- `events` : épreuves de la fenêtre portant au moins un TCN.
- `athletes` : athlètes TCN distincts de la fenêtre.
- `podiums` : même définition et même code que le compteur « tous rangs »
  (`rank_counters.all.podiums`), restreint à la fenêtre. Le chiffre de l'accueil
  ne peut pas diverger de celui de `/club`.
- Résultats en attente de validation exclus, comme partout ailleurs.
- Chemin standard : router `club` → service → repository. Ajout d'un
  endpoint, aucune modification de l'API publiée (Principe IV).

### Données déjà disponibles

- Chiffres de la saison et histogramme : `getStats({ scope: club, seasons:
  [saison en cours], federal_only })`, déjà appelé par `/club`.
- Tuile Résultats : `listEvents({ scope: club, page_size: 1 })`.
- Tuile Back-office : `useNavBadges`, déjà monté pour le sélecteur d'espace.
- Tuile Mon espace : `useSelectedAthlete` et la requête de saison de `MaSaison`.

L'accueil suit `SHORT_REVALIDATE_SECONDS`, comme `/club`. Une panne d'un appel
serveur autre que `last-outing` suit le patron d'erreur des pages publiques
(`error.tsx`).

## Tests

TDD, Principe III.

- **Backend** (`tests/test_repositories`, `tests/test_api`) : sortie sur un
  week-end (samedi et dimanche réunis), course isolée en semaine, aucune course
  (`null`), course de la saison précédente ignorée, résultats en attente
  exclus, `podiums` égal à `rank_counters.all.podiums` sur la même fenêtre,
  `federal_only` respecté, forme de la réponse.
- **Frontend** (vitest) :
  - bandeau : « Ce week-end » contre « Dernière sortie · … » selon la date,
    repli « Pas encore de course cette saison », valeurs finales présentes sans
    animation sous `prefers-reduced-motion`, résumé accessible de
    l'histogramme ;
  - tuiles : Encadrement et Back-office absentes sans pouvoir et pendant la
    lecture de la session, badge du Back-office, tuile Mon espace avec et sans
    athlète retenu ;
  - `/mon-espace` reprend les tests de l'ancien dashboard, sans la carte
    « Le club » ;
  - navigation : « Accueil » vers `/`, « Mon espace » vers `/mon-espace`,
    plus aucune référence à `/dashboard`.
- **Fin de branche** : revue de code, `ui-ux-review`, vérification sur la
  preview à 360 px et sur bureau.

## Découpage et exécution

Epic #1618 « Accueil carrefour », workflow epic de
`docs/gestion-de-projet.md` (branche d'epic, une PR par sous-issue) :

1. #1619 `feat(club): expose the club's last outing` : l'endpoint backend.
2. #1620 `feat(nav): move the personal dashboard to /mon-espace` : déplacement de
   la page, références, navigation.
3. #1621 `feat(home): turn / into a hub with the club's live banner and space tiles` :
   l'accueil.

L'ordre 1 → 2 → 3 garde un produit qui marche à chaque étape : après 2, `/`
redirige provisoirement vers `/mon-espace` dans la même PR, et 3 remplace cette
redirection par la page.

## Hors périmètre

- Multi-club (sélecteur, club dans l'URL, données).
- Bandeau défilant des temps forts, records club battus.
- Toute modification de `/club`.
- Contenu personnel nouveau dans Mon espace (epic #1360).
