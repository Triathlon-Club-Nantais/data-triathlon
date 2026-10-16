# Back-office : écrans d'administration

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## Composition des rôles (#240)

**Composition des rôles** (`admin/droits`, #240) — l'écran **n'invente aucun
regroupement** : `GET /admin/permissions` rend l'inventaire déjà rangé par
fonctionnalité, dans son ordre d'affichage, et `PermissionGrid` le reproduit
tel quel (`<fieldset>`/`<legend>`, cases natives). Cinq pièges à ne pas
rouvrir :

- `PATCH` n'envoie que les champs modifiés — `permissions` remplace
  l'ensemble, donc l'envoyer sur un simple renommage purge les codes périmés
  en silence.
- Un rôle `is_system` est **modifiable**, seule sa suppression est refusée.
- La non-amplification vaut **aussi dans la modale de création**, et plus
  durement : `create_role` soumet à `assert_may_grant` l'ensemble complet des
  codes, `update_role` seulement la différence symétrique. D'où un `figes`
  calculé une fois pour l'écran et passé aux **deux** grilles.
- `roles:read` et `roles:write` sont deux pouvoirs distincts. Le rail de
  navigation filtre sur le second mais n'est pas une garde : sans le test
  explicite, un porteur du premier obtient un éditeur d'apparence complète
  dont chaque geste finit en 403.
- Le panneau compare et affiche `base`, l'état serveur sur lequel il a été
  ouvert — pas la prop. `roles` se rafraîchit sous un panneau resté
  ouvert, et se fier à la prop renvoie l'ensemble figé à l'ouverture, effaçant
  la recomposition d'un autre administrateur.

Superutilisateur et session illisible : règle transverse « Session et
pouvoirs », restée dans `frontend/AGENTS.md`.

## Gestes destructifs : exceptions de rendu (#499)

La règle générale (couleur destructive et `DangerConfirm`) reste dans
`frontend/AGENTS.md`, « Gestes destructifs ».

Deux exceptions à la couleur portée par le `variant` plein, chacune
commentée sur place : la croix de retrait de rôle d'`UserRolesTable`, `ghost`
au repos et `destructive` au survol et au focus — une croix par badge,
plusieurs badges par ligne ; un bouton-icône dans un tableau dense qui pose
la couleur destructive par une teinte posée à la main plutôt que par le
variant plein, pour ne pas écraser ses voisins (`CoursesAdminTable`, la
corbeille et son crayon jumeau). Un critère à part, de rayon d'action et non
de rendu : un geste réparable mais dont la portée est l'ensemble des comptes
se signale en destructif malgré tout, variant plein compris
(`RevokeSessionsCard`, « Fermer toutes les sessions », qui déconnecte tout le
monde, vous compris — face à « Fermer les sessions » d'une seule adresse, qui
reste neutre).

## Retours utilisateurs (#500)

**Retours utilisateurs : une file, pas une liste** (#500, ADM-10) —
`FeedbackTable` ouvre sur « Nouveau » seul et filtre **côté serveur**
(`?status=`), les décomptes venant de `GET /admin/feedback/counts`. Quatre
points qui se re-cassent séparément :

- **La barre de filtres reste montée dans tous les états** — chargement,
  refus, résultat vide —, patron de `CoursesAdminTable` : la vue par défaut
  est filtrée, donc la retirer enfermerait un administrateur sans nouveaux
  signalements hors des trois autres statuts.
- **Le compteur, c'est le nombre porté par chaque entrée de la barre**, pas
  une phrase au-dessus : celle-ci redirait le même chiffre, et pour un statut
  sur quatre seulement.
- **Un seul contrôle de statut par ligne, et il est coloré.** Qui porte
  `feedback:manage` voit un `<select>` habillé du couple aplat/encre du
  statut ; les autres, un `Badge` du même couple. Un badge *et* un sélecteur
  côte à côte diraient deux fois la même valeur — et sans couleur du tout,
  « Nouveau » et « Ignoré » ont exactement le même poids visuel, ce que
  l'audit reprochait. Les couples viennent du thème pour la raison de
  `BatchRunList` : les variantes génériques de `Badge` ne tiennent pas 4,5:1
  sous 12 px.
- **La modale de détail est rendue hors de la cascade d'états**, pas dans la
  seule branche nominale : instruire depuis elle le dernier signalement d'un
  filtre vide la liste, et la modale disparaîtrait sous les doigts avant la
  promotion en issue. Symétriquement, « aucun retour utilisateur » ne
  s'affirme que si les décomptes le disent — une vue **filtrée** vide ne
  prouve rien sur la base, et le comptage peut échouer.
- **Le contrôle en ligne n'est jamais `disabled` pendant sa requête** —
  `aria-busy` et une opacité, la ré-entrée gardée dans le gestionnaire : un
  navigateur retire le focus d'un contrôle désactivé, et l'écran existe pour
  enchaîner les gestes au clavier. Quand le changement fait quitter la vue
  filtrée à la ligne, le focus est reposé sur la puce du filtre courant.
- **`--tcn-fill` ne sert pas de survol** : il vaut exactement `--background`
  (`#f4f3f0`), donc un survol à 1,00:1 — même piège que le `bg-muted` des
  squelettes. Les puces prennent `--tcn-orange-08`, et `cursor-pointer`,
  norme de `ui/button.tsx`.
- **`queryKeys.feedbackCounts()` vit sous le préfixe `["admin-feedback"]`**,
  celui de la liste : un changement de statut périme les deux, et
  l'invalidation existante les emporte alors d'un seul geste.

## Sommaire `/admin` et source unique des titres (#497)

**Sommaire `/admin` et source unique des titres** (#497, ADM-2/ADM-6) —
`/admin` n'est plus une impasse : `AdminIndex` rend une tuile par écran du
back-office, filtrée par `estVisible`, **la même règle que le rail** — un
écran annoncé d'un côté et tu de l'autre est un écran dont on ne sait plus à
qui il s'adresse. Le titre **et** la phrase d'un écran d'administration vivent
une seule fois, dans `nav.config.ts`, et sont rendus aux deux endroits par
`ecran(href)` : la page les passe à son `PageHeader`, la tuile les affiche.
Les tenir en double les avait déjà fait diverger (le rail annonçait « Gestion
des courses » quand l'écran s'intitulait « Épreuves »). `ecran()` **lève** sur
une entrée sans phrase : c'est une erreur de configuration, pas un cas à
couvrir en silence, et `nav.config.test.ts` la rattrape avant l'écran.
`ecran()` rend aussi `helpHref`, le lien « Aide » du `PageHeader` vers la
section du guide admin que nomme le `helpAnchor` de l'entrée (#1245). Une
ancre et non un import du guide : `nav.config.ts` est lu par le rail de
chaque page, et importer `GUIDE_ADMIN` y faisait entrer tout le texte du
guide. `nav.config.test.ts` échoue tant qu'une entrée vers `/admin`, quelle
que soit sa section, n'a pas d'ancre existante dans le guide. Corollaire du même lot : plus aucune entrée d'administration sans
`permission`, « Épreuves » ayant été la dernière — donc la seule proposée à
qui n'y peut rien faire. Enfin, `/admin/batches` **est** l'écran de
`batch:run`, et c'est `BatchRunList` qui porte la garde de `batch:read` : sans
ce pouvoir, la liste dit ce qui manque au lieu de partir en 403, et
`BatchLauncher` **dit** qu'il lance à l'aveugle plutôt que de laisser
`enCours` valoir silencieusement `false` — le refus du second lancement reste
au serveur (409). Trois points relevés en `ui-ux-review` du même lot, valables
bien au-delà : le **surtitre** vient lui aussi de la section (`ecran()` le
rend), sans quoi quatre écrans rangés sous « Administration » annonçaient
« Maintenance » ou « Exploitation » à l'arrivée ; un anneau de focus se pose
en **trait opaque** `--tcn-orange` (3,32:1 sur `--tcn-paper`), jamais en halo
`ring-ring/50` seul, qui tombe à 1,86:1 ; et `Skeleton` porte
`--tcn-grey-300` depuis que `bg-muted` s'est révélé être **exactement**
`--background` (`--tcn-fill` = `--tcn-paper` = `#f4f3f0`, ratio 1,00:1) —
`animate-pulse` n'animant que l'opacité, tous les squelettes du front étaient
invisibles.

## Sous-sections et files en tête du sommaire (#1246, #1232)

**Administration en sous-sections, files en tête du sommaire** (#1246, #1232) : chaque entrée d'« Administration » porte un `group` (À traiter,
Données, Paramétrage, Conformité, Gestes sans retour), rendu en intertitre
par le rail déplié et par `AdminIndex` ; les entrées d'un groupe se suivent
dans la table (`byGroup`), `nav.config.test.ts` le tient. Au rail, chaque
sous-section est un `role="group"` nommé, dans les deux états du rail, pour
que ses liens gardent leur place dans l'arbre (#428). Le sommaire met les files « À
traiter » en tête, avec le compteur de leur pastille (`useNavBadges`, même
nom accessible via `libelleCompteur`, « … » discret au premier chargement),
et ne les répète pas en tuiles. Toutes les
pastilles viennent d'**un** appel, `GET /admin/badge-counts` (#1385), demandé
pour un compte d'administration seulement : le serveur ne rend que les clés
que la session voit, « Validation des épreuves » comprise (cookie bénévoles,
illisible côté client). Le compte tient 5 min (deux revues le rejouent en
entier) et **toute mutation réussie l'invalide** (`MutationCache` de
`app/providers.tsx`) ; `useFileValidation`, qui n'écrit pas par `useMutation`,
l'invalide lui-même. La pastille de la revalidation compte les
épreuves sans avis humain, et sa file les montre par défaut
(`awaiting_review=true`). Sous les files, le porteur de `quality:override`
voit le tableau fournisseur × anomalie (`ProviderQualityTable`, #1366). La palette ⌘K mène aussi aux écrans : `AthletePicker`
reçoit les destinations visibles du rail, plus `/admin` et `/admin/guide`
pour un compte d'administration, les filtre sur place, en liens hors du
combobox des athlètes, et compte les écrans trouvés dans son statut.
