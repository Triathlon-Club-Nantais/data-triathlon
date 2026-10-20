# Mon espace en trois colonnes : design

Date : 2026-10-19. Voie Superpowers, brainstorming avec compagnon visuel (maquettes
`mon-espace-v1` à `v3`). Issue d'origine : #1657 ; epic de rattachement : #1667
(espace personnel, deuxième vague), qui prolonge #1360.

## Intention

La **fiche athlète** (`/athletes/[id]`) est la façade publique d'un athlète.
**Mon espace** (`/mon-espace`) en devient la version **personnelle** : on y
retrouve tout ce que montre la fiche (progression, répartition par saison,
toutes les épreuves, bénévolat, challenges, comparaison), et davantage :
indicateurs comparés à la saison précédente, graphiques, records, objectifs,
encarts contextuels. Le but est qu'un membre ouvre Mon espace pour **se voir
progresser** et y trouve toutes ses informations au même endroit.

## Décisions de l'utilisateur

- **Accès** : uniquement le membre **connecté** dont le compte est **rattaché à
  une fiche d'un club** (#1325). Les autres (visiteur, compte non rattaché)
  voient une invitation : se connecter, ou demander le rattachement de sa fiche
  (patron existant d'`InvitationAthlete` / parcours de rattachement).
- **Mise en page bureau en trois colonnes** : à gauche la navigation (inchangée),
  au centre l'essentiel, à droite des encarts « en plus ».
- **Centre** : « Mes chiffres » toujours visible, puis une **carte à onglets**.
- **Tout le catalogue est retenu** (on retirera plus tard si besoin) :
  courbe de classement relatif, épreuves par mois, splits face au club,
  répartition par discipline et format, ma place au club, mon dernier
  résultat, mes coéquipiers de course, prochain palier, carte de mes épreuves.
- **Records** : retenus, très appréciés.
- **Ajouts** : la liste de mes épreuves et mes actions de bénévolat.

## Contenu

### En-tête

Titre « Mon espace », saison(s) en titre, sélecteur de saisons (le même que
`/club` et l'accueil, `?seasons=`), sélecteur de disciplines. Tout ce qui suit
porte sur la sélection.

### Centre

**Mes chiffres** (carte pleine largeur du centre) : épreuves, podiums (général,
genre ou catégorie), km parcourus, temps total en course, meilleur classement
relatif (top %). Chacun avec l'écart face à la **saison précédente à la même
date** quand une seule saison est sélectionnée (ma proposition : comparer à date
égale évite de comparer une saison entamée à une saison complète) ; sans écart
quand plusieurs saisons sont sélectionnées. Lien « Récap de la saison passée »
(#1372).

**Carte à onglets**, dans cet ordre (ma proposition) :

1. **Progression** : courbe du classement relatif (top %) épreuve après
   épreuve, avec la saison précédente en pointillés ; histogramme de mes
   épreuves par mois (même langage visuel que l'accueil).
2. **Records** : par format calibré (XS à XL) et discipline, mon meilleur
   temps de la sélection face à mon record personnel toutes saisons, avec badges
   « record perso » et « 1re fois » ; réutilise le calcul des meilleurs temps
   de la fiche athlète (#1361).
3. **Disciplines** : répartition de mes épreuves par discipline et format ;
   mes splits (natation, vélo, course) face à la médiane du club sur le même
   format, uniquement quand les splits sont fiables.
4. **Épreuves** : la liste complète de mes épreuves de la sélection, comme sur
   la fiche athlète (mêmes colonnes, mêmes gestes), avec l'export CSV (#1375).
5. **Bénévolat** : mes actions de bénévolat validées et mes déclarations en
   cours (#1672).
6. **Objectifs** : le bloc existant « Mes objectifs » (#1373, #1668, #1669).

Les challenges de l'athlète (présents sur la fiche) vont dans l'onglet
Épreuves, sous la liste (ma proposition).

### Droite

Encarts, de haut en bas (ma proposition) :

- **Mon dernier résultat** : épreuve, date, temps, place, badge record perso,
  lien vers la fiche, bouton « Ma carte résultat » (#1371).
- **Validation de ma saison** : épreuves comptées et bénévolat (#1671).
- **Ma place au club** : rang parmi les athlètes actifs du club sur la
  sélection (`/club/roster/rank`), évolution face à la saison précédente.
- **Prochain palier** : un objectif implicite calculé (« encore 2 épreuves
  pour égaler votre meilleure saison »), barre de progression.
- **Mes coéquipiers de course** : les membres avec qui j'ai le plus couru sur
  la sélection, avec « Me comparer » (#1675).
- **Carte de mes épreuves** : petite carte des lieux de mes épreuves, réutilise
  le composant de la carte du club en version réduite.
- **Mes demandes de rattachement** : seulement s'il y en a (#1670).

### Mobile

Une seule colonne : en-tête, Mes chiffres, onglets (défilables
horizontalement), puis les encarts de droite. Pas de défilement horizontal de
page à 360 px.

## Contraintes

- Écran public au sens du design system : `components/tcn/`, jetons `--tcn-*`,
  vouvoiement, « épreuve », « athlète », 44 px, focus `--tcn-orange`,
  contrastes 4,5:1 (texte) et 3:1 (graphiques), graphiques avec résumé
  accessible, animations coupées sous `prefers-reduced-motion`.
- Session lue côté client par `useHydratedSession` (règle #1090).
- Données personnelles : rien de ce qui est privé (objectifs, demandes,
  déclarations) n'apparaît ailleurs que dans Mon espace ; la fiche publique ne
  change pas. Les oppositions RGPD (#1673, #1615) s'appliquent aux coéquipiers
  affichés.
- `/api/v1` : ajouts seulement (Principe IV).
- Multi-club (#1677, #1686) : les calculs « au club » portent sur le club du
  membre ; ne pas figer `TCN` dans de nouveaux calculs.

## Non-objectifs

- Refaire la fiche athlète publique.
- Page compte et export des données du compte (#1663, #1674).
- Saisie de nouvelles données (objectifs à part, déjà livrés).

## Anti-objectifs

- Une page qui recopie la fiche publique sans rien de plus.
- Des chiffres qui contredisent ceux de `/club` ou de la fiche athlète (même
  définition de podium, même validation).

## Laissé au constructeur

- Le découpage en sous-issues et leur ordre (ma proposition : 1. squelette
  trois colonnes + garde d'accès + Mes chiffres ; 2. onglets Épreuves,
  Bénévolat, Objectifs (réemploi) ; 3. Records ; 4. Progression ;
  5. Disciplines et splits ; 6. encarts de droite par lots).
- Les endpoints à ajouter et leur forme, en réutilisant d'abord
  `/athletes/{id}` et `/club/roster/rank`.
- Le choix des bibliothèques de graphique (réutiliser les composants SVG
  existants de `components/charts/`).

## Arbitrages après relecture (choix de l'agent, à vérifier)

Une relecture « constructeur » a posé des questions ; celles qu'un constructeur
ne pouvait pas trancher seul sont réglées ici, chacune comme choix de l'agent.

1. **Garde d'accès** : Mon espace lit l'athlète **rattaché au compte**
   (`session.athlete`, via `useHydratedSession`), et non plus l'« athlète
   retenu » du navigateur (`tcn-athlete`), qui reste pour la fiche publique et la
   palette ⌘K. Les onglets dérivés de données publiques (Épreuves, Records,
   Disciplines, Progression, Mes chiffres) appellent les endpoints publics
   existants avec cet identifiant ; les données privées (objectifs, demandes,
   déclarations, validation) passent par leurs endpoints authentifiés, existants
   ou livrés par leurs issues. Pas d'agrégat `/me` nouveau tant qu'un besoin de
   performance ne l'impose pas.
2. **Classement relatif** : c'est le ratio déjà calculé par la fiche athlète
   (`rankRatio`, `lib/utils/ranking.ts`, #677 : place au général / classés de
   l'épreuve, rien pour une épreuve non fiable ou incomplète) et déjà tracé par
   `ProgressionChart`. Aucun nouveau calcul.
3. **Saison précédente « à la même date »** : la même date un an plus tôt
   (les saisons ont des bornes fixes au 1er septembre). Écart affiché pour les
   cinq chiffres, seulement quand une seule saison est sélectionnée.
4. **Dépendances** : déjà livrées #1361, #1371, #1372, #1373, #1375. Ouvertes :
   #1668 à #1673, #1675, #1615. Un onglet ou encart qui dépend d'une issue non
   livrée n'apparaît pas tant qu'elle ne l'est pas (pas de faux contenu) ; les
   sous-issues de ce design sont ordonnées en conséquence.
5. **Prochain palier** : le plus proche de deux paliers, « égaler votre
   meilleure saison en épreuves » et « égaler votre meilleure saison en
   podiums » ; rien à afficher si la saison en cours dépasse déjà les deux.
6. **Coéquipiers de course** : les membres du club présents sur les mêmes
   épreuves (même `course`) dans la sélection, triés par nombre d'épreuves
   communes, 3 au plus ; calcul côté serveur (nouvel endpoint, ajout seul), qui
   exclut les athlètes ayant une opposition (#1673, #1615). « Me comparer »
   ouvre la comparaison existante de la fiche athlète avec le coéquipier
   présélectionné (#1675).
7. **Multi-club** : « le club » est le club de la fiche rattachée tel que le
   modèle l'exprime aujourd'hui (TCN) ; les nouveaux calculs passent par les
   critères d'appartenance existants (`counts_for_tcn`, `tcn_clause`) plutôt que
   par une constante, pour que #1686 n'ait qu'un seul endroit à changer.
8. **Carte de mes épreuves** : les épreuves de la carte du club portent déjà des
   coordonnées (`lat`/`lng`, géocodage existant) ; la mini-carte réutilise ces
   données, filtrées sur mes épreuves.
