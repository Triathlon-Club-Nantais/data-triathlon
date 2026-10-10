# Navigation en trois espaces : design

Date : 2026-10-10. Voie Superpowers. Source : parcours de la préprod
(`data-triathlon-tcn-preview.vercel.app`, 377 px, compte portant tous les
pouvoirs) et lecture de `frontend/components/layout/nav.config.ts`.

## Constats

1. **Deux accueils qui se recouvrent.** `/dashboard` et `/club` rendent tous
   deux la saison courante, les compteurs Général/Catégorie/Genre et les
   podiums du club.
2. **La barre basse change après la lecture de la session.** Premier rendu :
   Accueil, Résultats, Espace club, Validation. Après hydratation : Accueil,
   Résultats, Carte, Espace club, Plus. Les onglets bougent sous le doigt.
3. **Fiche épreuve, côté admin.** Cinq boutons (Re-scraper, Corriger, Avis de
   fiabilité, Fusionner, Supprimer) occupent le premier écran mobile ; les
   résultats passent sous la ligne de flottaison. Chargement observé à plus
   de 15 s sur la préprod.
4. **Tiroir à plat.** Club, Administration (14 entrées, 5 groupes), Gestion des
   utilisateurs (4) et Jeunes (3) se suivent : environ 25 liens mêlés à la
   navigation publique.
5. **Le sommaire `/admin` n'a aucune entrée de navigation.** Seule la palette
   ⌘K y mène, alors qu'il porte les files « À traiter » et leurs compteurs.
6. **Les compteurs ne se voient qu'en ouvrant le tiroir.**

## Décisions de cadrage

- Usage du back-office : mixte, desktop et mobile à égalité.
- Accueil et Club restent deux pages, distinguées par leur contenu.
- Jeunes, et à terme les fonctions de vie du club (remplacement d'Epeak,
  #870), vivent dans un espace « Encadrement » distinct du back-office.

## Les trois espaces

| Espace | Visible pour | Entrées |
| --- | --- | --- |
| **Résultats** (public) | tous | Accueil (personnel : ma saison, mes épreuves), Résultats, Club (collectif : podiums, effectif, Athlètes par saison, Bénévolat, Validation des épreuves), Carte (avant-première) |
| **Encadrement** | `can_supervise` | Jeunes, Calendrier, Appel, Crédits bénévoles |
| **Back-office** | `can_administer` | Sommaire (entrée de l'espace), puis les groupes À traiter, Données, Paramétrage, Utilisateurs, Conformité, Gestes sans retour, et le guide d'administration |

- « Validation des épreuves » (`/benevoles`) reste publique : sa porte est le
  mot de passe bénévoles, un bénévole n'a pas de compte.
- « Bénévolat » (`/benevolat`, déclaration de crédits) reste dans Club ; sa
  validation (`/admin/benevolat`) passe dans Encadrement.
- Les quatre écrans de « Gestion des utilisateurs » deviennent le groupe
  « Utilisateurs » de la section admin.
- L'Accueil perd ses blocs collectifs en double (podiums club, compteurs
  Général/Catégorie/Genre), qui ne vivent plus que sur Club. Il garde
  « Ma saison », les dernières épreuves, et un renvoi vers Club.

## En-tête, rail, barre mobile

**Sélecteur d'espace.** Dans l'en-tête, à côté du logo : `TCN · Résultats ▾`.
Il liste les espaces ouverts au compte, chacun avec son badge (Back-office :
total des files « À traiter »). Un seul espace accessible : pas de sélecteur.
L'espace courant se déduit du préfixe d'URL (`/admin`, `/encadrement`, sinon
Résultats), sans état stocké. Sur mobile, même place, menu en `Sheet`.

**Rail desktop.** Il ne rend que les sections de l'espace courant ; `Entree`,
le cookie de largeur et le repli ne changent pas. En pied du rail public, une
entrée « Back-office · N » sert de raccourci aux administrateurs.

**Barre basse mobile, par espace** (bornée par `BOTTOM_BAR_MAX`) :

- Résultats : Accueil, Résultats, Club, Rechercher. Fixe, **indépendante de la
  session**, ce qui supprime le saut du constat 2.
- Encadrement : Jeunes, Appel, Calendrier, Bénévolat.
- Back-office : Sommaire (badge total), Épreuves, Identités, Rechercher, Plus.

« Ajouter une épreuve » reste dans la barre du haut, dans tous les espaces.

**Fiche épreuve.** Les cinq gestes d'administration passent dans un menu
« Gérer l'épreuve ▾ » (`ui/dropdown-menu`) sous le titre.

## Routes, gardes, configuration

- `/admin/jeunes/**` devient `/encadrement/jeunes/**`, `/admin/benevolat`
  devient `/encadrement/benevolat`. `/encadrement` redirige vers le premier
  écran ouvert au compte. Aucune redirection depuis les anciennes URL (écrans
  internes, pas de compatibilité ascendante).
- `app/encadrement/layout.tsx` applique la garde de `app/admin/layout.tsx`
  (session, pannes passantes, refus rendu sur place) sur `can_supervise`. La
  logique commune est extraite dans une fonction partagée.
- Le callback SSO mène au premier espace ouvert : Back-office, sinon
  Encadrement, sinon Accueil.
- `nav.config.ts` : champ `space: "public" | "encadrement" | "admin"` sur
  chaque `NavSection`. `ecran()`, `estVisible`, `byGroup`, `useNavBadges` ne
  changent pas. La palette ⌘K liste les écrans de tous les espaces
  accessibles. `AdminIndex` ne liste que le back-office.
- Backend : `permissions.administers()` exclut les fonctionnalités
  d'encadrement (`FEATURE_JEUNES`, validation des crédits bénévoles) ; un
  nouveau `supervises()` alimente `can_supervise` dans `GET /auth/me`. Champ
  ajouté, donc conforme au Principe IV.

## Couches de livraison

Chaque couche est livrable seule, avec sa PR et sa vérification en préprod,
puis `ui-ux-review` au déclenchement de l'utilisateur.

| Couche | Contenu | Tests |
| --- | --- | --- |
| 0. Correctifs indépendants | barre basse stable dès le premier rendu ; menu « Gérer l'épreuve » ; issue de sondage sur la lenteur de la fiche épreuve | `AppNav.test.tsx` : onglets identiques avant et après session ; test de `CourseAdminActions` |
| 1. Back-office séparé | `space`, rail et tiroir filtrés par espace, sélecteur, entrée « Back-office · N », groupe Utilisateurs | `nav.config.test.ts` (espace par section, groupes contigus) ; `AppNav.test.tsx` (aucun lien admin dans l'espace public, pas de sélecteur pour anonyme ou adhérent) |
| 2. Espace Encadrement | `supervises()`/`can_supervise`, déplacement des routes, garde partagée, atterrissage SSO | pytest `administers`/`supervises` et `/auth/me` ; `routes-garde-site.test.ts` ; garde Encadrement ; `page-titles.test.tsx` |
| 3. Barre mobile par espace | onglets Encadrement et Back-office, badge total | `AppNav.test.tsx` à 375 px : borne `BOTTOM_BAR_MAX`, onglet actif |
| 4. Accueil et Club distingués | retrait des blocs collectifs de `/dashboard`, renvoi vers Club | tests des pages `dashboard` et `club` |

## Hors périmètre

- La lenteur de la fiche épreuve : un sondage d'abord, son correctif ensuite.
- La palette ⌘K, inchangée.
- L'identité visuelle, inchangée.
