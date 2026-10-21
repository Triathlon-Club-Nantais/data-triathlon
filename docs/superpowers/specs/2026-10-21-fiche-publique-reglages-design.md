# Réglages de la fiche publique par le membre rattaché (#1692)

Epic #1667, milestone v0.9.0 (gel jeudi 22/10 au soir). Brainstorm du 21/10/2026
avec l'utilisateur. Version la plus petite qui marche de bout en bout.

## Intention

La fiche athlète est la façade publique (derrière le code d'accès du site), Mon
espace la version personnelle. Le membre qui a rattaché sa fiche (#1325) n'a
aujourd'hui aucune prise sur ce qu'elle montre. On lui donne deux gestes :
**masquer** trois blocs d'analyse, et **ajouter** des liens, un objectif public et
un résultat épinglé. Les résultats eux-mêmes restent toujours visibles :
l'opposition (#1673) est le seul chemin pour les retirer.

## Décisions de l'utilisateur

- **Masquables**, trois interrupteurs, tout visible par défaut (rien ne change
  pour qui ne touche à rien) :
  - records / meilleurs temps (`BestTimesCard`) ;
  - courbe de progression (carte « Progression », `ProgressionChart`) ;
  - comparaison avec un autre athlète (`AthleteComparisonChart`).
- **Non masquables**, et pourquoi : compteurs (`StatCard`), répartition par
  saison et pastille catégorie se relisent dans le tableau des résultats ; les
  masquer donnerait une fausse impression de confidentialité. Les défis
  (`AthleteChallenges`) sont collectifs, ils restent.
- **Liens** vers ses profils sportifs : jusqu'à 3.
- **Objectif public** : un seul, choisi parmi ses objectifs de Mon espace.
- **Résultat épinglé** : un seul, parmi ses propres résultats validés, affiché en
  tête de fiche.
- **Écartés** : présentation en texte libre (refusée) ; photo de profil (reportée,
  discussion #1790).
- **Où ça se règle** : une carte « Ma fiche publique » dans Mon espace,
  enregistrée côté serveur.

## Règles

### Liens (frontière de confiance)

- `https` seulement, 200 caractères au plus, au plus 3, sans doublon.
- Hôte dans une liste fermée, sous-domaines compris : `strava.com`,
  `garmin.com` (Garmin Connect est `connect.garmin.com`), `polar.com` (Polar Flow
  est `flow.polar.com`), `suunto.com`. Comparaison sur l'hôte analysé, jamais
  sur la chaîne (`https://strava.com.evil.example` est refusé, `user@host` et
  ports refusés).
- Aucun libellé libre : le libellé (« Strava », « Garmin Connect », « Polar
  Flow », « Suunto ») se déduit du domaine, côté serveur.
- Validation **côté serveur** (422 en français si refusé) ; le front peut
  pré-valider mais ne fait pas foi.
- Rendu : `<a target="_blank" rel="noopener nofollow ugc">`.

### Objectif public

- Un seul objectif public par compte (même patron que `major`, un seul par
  compte et par saison, tenu par le service).
- Affiché seulement s'il porte sur la **saison en cours** : un objectif d'une
  saison passée ne s'affiche plus, sans geste du membre.
- Supprimer l'objectif retire son affichage (il est la donnée, pas une copie).
- Sa progression publique se calcule comme dans Mon espace, sur les résultats
  validés de la fiche (déjà publics).

### Résultat épinglé

- Choisi parmi les résultats **validés** de la fiche rattachée (porteur ou
  équipier d'un relais, lecture « par athlète » via `carried_by`).
- Vérifié **à la lecture**, pas seulement à l'écriture : s'il n'appartient plus à
  la fiche (réattribution, fusion vers une autre fiche, anonymisation), n'est
  plus validé ou n'existe plus, l'épingle ne s'affiche pas.

### Cohérence avec le rattachement, l'opposition et les jeunes

- Les réglages appartiennent au **compte**, pas à la fiche. La fiche publique
  applique ceux des comptes rattachés (`users.athlete_id`) au moment de la
  lecture.
- **Détachement** (par le membre ou le club) : plus de compte rattaché, la fiche
  redevient la fiche par défaut. Les réglages restent sur le compte (ils
  resservent à un nouveau rattachement ; l'épingle se revérifie à la lecture).
- **Suppression du compte** (#1326) : réglages et liens partent avec lui (table
  possédée, `_OWNED_TABLES`).
- **Opposition** : la fiche est supprimée et ses résultats anonymisés ; aucun
  compte n'est plus rattaché à une fiche qui nomme la personne, donc liens,
  objectif et épingle ne peuvent s'afficher sur une fiche « Anonyme ». Rien ne
  doit jamais rendre un lien sur une fiche anonyme
  (`opposition_service.is_anonymous`), y compris par une épingle vers un
  résultat devenu anonyme.
- **Fiche masquée au public** (#1615, saisies en attente seules) : 404 comme
  aujourd'hui, rien de neuf ne s'y affiche.
- **Jeunes** (#881) : une ligne jeune n'apparaît nulle part ; un résultat jeune
  ne peut donc pas être épinglé (même filtre que la liste publique).

### Respect côté serveur

`GET /athletes/{id}` porte les réglages (blocs masqués, liens, objectif public,
id du résultat épinglé) et la page, rendue côté serveur, **n'émet pas** les blocs
masqués dans son HTML. Limite assumée, dite dans l'interface : les blocs masqués
se recalculent depuis les résultats, qui restent publics ; la fiche reste aussi
cherchable comme adversaire depuis la comparaison d'une autre fiche.

## Données

Choix du concepteur (à corriger au plan si besoin) :

- Table possédée par le compte, une ligne par compte (`user_id` unique), ajoutée
  à `_OWNED_TABLES` et à la cascade ORM de `User` : les trois booléens de
  masquage, les liens (liste JSON d'URL normalisées) et
  `pinned_participation_id` (FK `participations`, `ON DELETE SET NULL`, inerte
  en SQLite, d'où la revérification à la lecture).
- Objectif public : booléen sur `season_goals`, pas une référence depuis la
  table de réglages (la suppression de l'objectif suffit alors).
- Une migration Alembic. Base : tête courante de `origin/main` au moment
  d'écrire (`a1745e7c0b2d` au 21/10) ; rebase et `down_revision` repointé si une
  autre migration arrive avant la fusion.

### Plusieurs comptes sur une même fiche

`users.athlete_id` est N vers 1 (FR-003). Choix du concepteur : un bloc est
masqué si **un** des comptes rattachés le masque (le plus protecteur gagne) ;
liens, objectif et épingle ne s'affichent que si **un seul** compte est
rattaché. La carte de Mon espace le dit au membre dans ce cas.

## API (sous `/api/v1`)

- Lecture et écriture des réglages du compte connecté sous `/auth/me/…`, sur le
  patron de `/auth/me/goals`, réservées à un compte rattaché (sinon refus).
- Rendre public un objectif : par l'écriture d'objectif existante ou une route
  dédiée, au choix du plan.
- `GET /athletes/{id}` : champ **ajouté**, optionnel, neutre quand rien n'est
  réglé (Principe IV : on n'altère pas la réponse existante).

## Interface

- Mon espace : carte « Ma fiche publique » (trois interrupteurs, jusqu'à 3
  liens, choix de l'objectif public et du résultat épinglé), avec un lien vers
  sa fiche pour vérifier le rendu, et la phrase sur la limite de
  confidentialité.
- Fiche athlète : liens et objectif public dans l'en-tête ; résultat épinglé en
  tête de contenu ; blocs masqués absents. Les visiteurs ne voient aucune trace
  d'un bloc masqué.
- Microcopie en français, accessible (interrupteurs étiquetés, état annoncé à
  l'enregistrement par une région `AnnonceStatut` montée d'office).

## Hors périmètre

- Présentation libre, photo (#1790), masquage d'autres blocs.
- Retirer la fiche de la recherche ou de la comparaison des autres fiches.
- Opposition à la publication des résultats (#1673), badge de fiche rattachée.

## Laissé au concepteur du plan

- Nom de la table et des routes, forme exacte du champ ajouté à
  `GET /athletes/{id}`.
- Emplacement exact de la carte dans Mon espace et du résultat épinglé sur la
  fiche ; réutilisation des composants existants (`ObjectifMajeur`,
  `EventsTable`) plutôt que de nouveaux.
- Découpage en tâches TDD.
