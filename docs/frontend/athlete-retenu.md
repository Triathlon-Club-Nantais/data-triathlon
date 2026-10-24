# Athlète retenu et fiches publiques

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## Pas de cookie miroir (#467)

**L'athlète retenu ne franchit pas la frontière serveur : pas de cookie
miroir** (#467 — arbitrage du cluster, il vaut aussi pour #502, #503, #504).
Le stock `tcn-athlete` vit en `localStorage` ; un écran qui s'y adapte le lit
**côté client** par `useIsSelectedAthlete(id)`
(`components/layout/AthletePicker.tsx`, à côté du stock), jamais par une copie
en cookie relue en rendu serveur. Trois raisons, dans cet ordre.

- **Aucun rendu serveur n'en a besoin.** Les quatre usages du cluster sont de
  la mise en avant (pastille, liseré, ancre) et un rapprochement de chiffres
  que l'API publique sert déjà : rien ne se filtre, ne se trie ni ne se
  récupère sur cette valeur. Un cookie serait un transport sans destinataire.
- **Le coût de cache est réel dès qu'on sort du profil.** Ce n'est pas
  `/athletes/[id]` qui le paierait — le build le donne `ƒ`, `serverFetch`
  l'appelant en `no-store` —, c'est le cookie **en tant que transport** :
  `/mon-espace`, `/club` et `/ajouter` tournent sur la fenêtre de revalidation
  de 30 s mesurée par #352, et un rendu qui dépend d'un cookie par visiteur
  n'est plus partageable. C'est le même raisonnement qui a déjà valu à
  `serverFetch` de ne pas relayer les cookies (voir son commentaire dans
  `lib/api/server.ts`) : #502 est exactement la page concernée.
- **Un miroir, c'est deux stocks à tenir synchronisés**, dont un éditable par
  l'utilisateur et un envoyé au serveur à chaque requête, sans qu'aucune
  donnée personnelle n'ait à y aller.

Le prix, assumé : `useSyncExternalStore` rend `false` au serveur, donc le
signifiant d'état n'est **jamais dans le HTML initial** et apparaît à
l'hydratation — la boîte qui le porte réserve sa place (`.tcn-avatar-frame`)
pour que son apparition ne déplace rien. Seul un besoin **serveur** authentique
— une requête API qui dépendrait de l'athlète retenu — rouvrirait
l'arbitrage ; de la mise en avant, non.

## Les surfaces qui propagent l'athlète retenu (#503)

**Les surfaces qui propagent l'athlète retenu** (#503) : la pastille
« Mes résultats » de `/resultats`, la ligne marquée « Vous » et le bouton
« Aller à ma ligne » du classement d'épreuve. Elles lisent
`useSelectedAthlete()` (`components/layout/AthletePicker.tsx`, à côté de
`useIsSelectedAthlete`). `AppNav` ne lit pas le stock (#1828, « Mon espace »
mène à ses propres résultats) : sa palette l'écrit en mode désignation.
Le snapshot de `useSelectedAthlete()`
est **mémorisé sur la chaîne brute du stock** :
`readAthlete()` reconstruit un objet à chaque lecture, et le rendre tel quel
fait rendre `useSyncExternalStore` en boucle. Trois invariants :
**aucun filtre n'est appliqué au chargement** — chaque geste demande un clic
et se révoque par une commande déjà à l'écran (le chip `Athlète : … ✕`, le
bandeau « … · Effacer » de #485) ; **le liseré orange gauche du classement
reste réservé à `is_tcn`**, d'où le fond `--tcn-orange-08` et le chip
« Vous », qui porte le sens que la couleur seule ne peut pas porter
(WCAG 1.4.1) ; et **« Aller à ma ligne » cherche, il ne saute pas** —
l'ordre d'affichage est une propriété de la requête SQL depuis #163, le
front ne sait pas calculer « ma page », et `q` y mène à coût backend nul.

**Constaté sur #502**, premier consommateur réel de l'arbitrage : la bande
« Ma saison » lit le stock par `useSelectedAthlete()` — pendant de
`useIsSelectedAthlete`, ajouté à côté de lui dans `AthletePicker.tsx`,
mémoïsé sur la chaîne brute du `localStorage` plutôt que sur l'objet
reconstruit — puis appelle `apiClient.getAthlete(id, { seasons,
federal_only })`. C'est le **premier appel navigateur** de `/athletes/{id}`,
jusque-là lue par le seul rendu serveur de la fiche athlète ; les deux
filtres y ont été ajoutés **optionnels et neutres par défaut**, pour que
« mes » chiffres se comptent sur exactement la même base que ceux du club
rendus au-dessus. Le besoin serveur qui aurait rouvert l'arbitrage n'est
donc pas apparu : le filtrage est passé dans la requête, pas dans le rendu,
et `/mon-espace` garde sa fenêtre de revalidation de 30 s partagée entre tous
les visiteurs. Une dimension n'est **pas** partagée, elle : le club se
compte sur `for_stats(club_only=True)` (`tcn_clause`), quand
`list_for_athlete` n'a délibérément aucune clause de club (FR-019,
`backend/app/api/AGENTS.md`) — une participation dont le club diffère ou
est vide compte donc pour l'athlète sans compter pour le club. Assumé, pas
réglé : #503 et #504 en hériteront. Depuis #1695, la bande a été remplacée par
Mon espace lié à la session : il lit l'athlète rattaché au compte, non plus
celui choisi dans le navigateur.

Deux règles s'attrapent en passant, valables pour #503 et #504 : le podium
d'un athlète doit se calculer sur le **même `?rank=`** que les compteurs
club (`lib/utils/club-aggregate.ts`, `bestRank`/`isPodium`, miroir de
`stats_service._rank_counters` — `ma-saison.ts` y délègue depuis la revue
finale de #502), et un bloc client monté au-dessus de contenu serveur
réserve sa hauteur dès l'hydratation — sinon le retour du fetch ajoute un
**second** décalage au premier.

Une troisième, trouvée en revue de #502 : une région `AnnonceStatut` se
monte **inconditionnellement**, texte vide (`""`) quand il n'y a rien à
annoncer, jamais insérée au moment où son texte apparaît — une région ARIA
live n'annonce que les changements observés **après** son enregistrement, et
une région déjà pleine à l'injection est le cas que NVDA, JAWS et VoiceOver
laissent tomber. Les tests jsdom passent quand même : ils ne vérifient que
le texte du DOM. Tous les autres consommateurs du dépôt le faisaient déjà
(`PodiumsList.tsx`, `EventList.tsx`,
`RaceFinishers.tsx`).

## Hiérarchie des commandes de la fiche athlète (#753)

**Hiérarchie des deux commandes en tête de fiche athlète, conditionnelle au
pouvoir** (#753) — `AthleteHeaderActions.tsx` lit `athletes:write` et
décide ordre et variant de `AthleteSelection` et `AthleteAdminPanel` : sans
ce pouvoir, rien ne change (sélection primaire, corrections absentes) ;
avec, « Corriger la fiche » passe en tête et en primaire, la sélection en
secondaire — sa tâche répétée profil après profil l'emporte sur une action
self-service hors sujet pour ce visiteur. Le bénéfice affiché sous le
bouton de sélection **reste visible** malgré la relégation (arbitrage de
l'issue) : seul `primary` change son variant, jamais le paragraphe.

Les sept gestes d'administration de la fiche (`AthleteAdminPanel`,
`AthleteOppositionAction`, `ParticipationAdminActions`, `AthleteDetachAction`,
`SeasonValidationPanel`, `VolunteerActionsList`, `AthleteVariantsPanel`) ne
s'importent jamais statiquement sur la route (#1582). Six passent par
`components/athletes/AdminGates.tsx`, en `next/dynamic` derrière un premier tri
de pouvoir, sur le motif de `CourseAdminActions`, chacun gardant sa propre
garde exacte. `AthleteAdminPanel` est importé par `AthleteHeaderActions`
lui-même, qui n'applique la hiérarchie à pouvoir qu'une fois le module arrivé :
la bascule reste d'un seul rendu. Un visiteur sans pouvoir n'en télécharge
rien ; `AdminGates.test.tsx` refuse leur import statique depuis la route.

## Gestes d'administration sur la fiche épreuve (#1244)

**Gestes d'administration sur la fiche épreuve** (#1244) :
`CourseAdminActions` réutilise les fenêtres du back-office (correction,
suppression, verdict de fiabilité, fusion) sans les recopier. Elles exposent
un rappel de succès optionnel (`onSaved`, `onDeleted`, `onDecided`,
`onMerged`) pour que la page serveur se rafraîchisse, ou quitte une fiche qui
n'existe plus (`/resultats` après suppression, l'épreuve conservée après une
fusion qui absorbe la fiche consultée). La fusion y choisit sa cible par
recherche libre (nom ou numéro, `GET /courses`), **sans contrainte de date**,
ce que `/admin/doublons` ne sait pas rapprocher ; le backend ne l'interdit pas.
`CourseAdminActions` n'est que la garde de pouvoir : le panneau
(`CourseAdminPanel`) et ses quatre fenêtres se chargent en `next/dynamic`
derrière elle, rien n'est téléchargé pour un visiteur sans pouvoir.
Les gestes se rangent sous un seul menu « Gérer l'épreuve » (#1301), chaque entrée
sous son pouvoir, la fusion et la suppression en `variant="destructive"` :
quatre boutons côte à côte repoussaient le classement sous la ligne de
flottaison sur mobile.

## La fiche du compte rattaché (#1325)

Un compte rattaché à sa fiche (`session.athlete`) n'a plus de choix à faire :
`SessionAthleteSync` (`app/providers.tsx`) écrit cette fiche dans le stock
`tcn-athlete`, et toutes les surfaces ci-dessus la suivent sans lire la
session. Le détachement vide le stock, y compris fait depuis un autre appareil
(marqueur `tcn-athlete-from-session` posé à côté du stock) ; une déconnexion le laisse, comme
avant. Les gestes de changement sont masqués pour lui : ni « Choisir cet
athlète » ni « C'est moi » sur une fiche (`AthleteHeaderActions` rend « Votre
fiche » ou le lien vers la sienne), et la palette demandée par `OPEN_PICKER_EVENT` s'ouvre en simple recherche. Un
connecté sans rattachement garde la sélection locale et se voit proposer
« C'est moi » (`components/athletes/AthleteClaimAction.tsx`).

## Carte résultat à télécharger (#1371)

« Télécharger l'image » sur la page détail d'un résultat, pour le seul compte
rattaché à la fiche du résultat, validé et individuel (un relais nomme des
équipiers). PNG 1080×1350 rendu **dans le navigateur** : `lib/result-card.ts`
sépare le modèle (`resultCardModel`, la seule ligne de l'adhérent), le dessin
(`drawResultCard`, un contexte 2D quelconque) et le téléchargement. Cette
séparation permet de passer le dessin côté serveur (`next/og`) si les appareils
des adhérents s'avèrent trop lents. Aucune URL publique ni balise OG : le site
reste derrière le code d'accès.

## Réglages de la fiche publique (#1692)

`GET /athletes/{id}` porte `public_page` (`hidden`, `links`, `goal`,
`pinned_participation_id`). La page `athletes/[id]/page.tsx` le lit côté
serveur et **ne rend pas** un bloc masqué (`best_times`, `progression`,
`comparison`) : ni CSS, ni `hidden`, le HTML servi au visiteur ne le contient
pas. Une fiche sans réglage (`public_page` neutre) se rend comme avant.

- Liens, objectif et résultat épinglé (`components/athletes/PublicPageExtras.tsx`)
  : liens et objectif sous les pastilles de l'en-tête, résultat épinglé en tête
  de la pile. Les liens sont des `<a target="_blank" rel="noopener nofollow ugc">`
  portant le libellé fourni par le serveur (`Strava`, `Garmin Connect`,
  `Polar Flow`, `Suunto`), jamais un libellé saisi.
- Un épinglage absent de `participations` (réattribué, anonymisé, en attente)
  ne rend rien, silencieusement.
- Plusieurs comptes rattachés à une fiche : un bloc est masqué dès qu'un compte
  le masque ; liens, objectif et épinglage ne s'affichent que si un seul compte
  est rattaché (règle appliquée par le serveur).
- Limite de confidentialité assumée : masquer un bloc retire son affichage, pas
  la donnée, que l'API `/athletes/{id}` continue de servir (les participations
  restent publiques derrière le code d'accès du site).
- `libelle`, `progression`, `hms` et `joursAvant` vivent dans
  `lib/utils/season-goal.ts` (importés par `SeasonGoals.tsx`, `RecapObjectifs.tsx`, `ObjectifMajeur.tsx`) : un composant
  serveur ne peut pas appeler une fonction exportée d'un module `"use client"`.
