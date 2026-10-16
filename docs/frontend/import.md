# Import d'une épreuve et saisie manuelle

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## Ce que l'import dit pendant, et après (#491)

**Ce que l'import dit pendant, et après** (#491) — trois points qui se
re-cassent séparément, et qui tiennent tous à une seule donnée : la **cause**
de l'échec, que `importEventStream` jette dans une `ApiError` plutôt que dans
une `Error` nue.

- `useImportStream` expose `errorStatus` : `null` = le flux s'est ouvert
  avant d'annoncer l'échec, donc la page **est** en cause ; `0` = coupure
  réseau ; sinon le statut HTTP du refus. `TcnScrapeForm` en tire trois
  écrans — plafond de débit (décompte sur `retryAfter`, l'en-tête
  `Retry-After` de `deps.py`), service muet (« Réessayer »), lecture
  impossible (saisie manuelle). **`reportPendingProvider` n'est appelé que
  dans le troisième** : signaler un lien Klikego parfaitement supporté au
  back-office parce que le plafond horaire était atteint polluait
  `pending-providers` sans qu'aucun écran ne le dise.
- Le bilan rend les **cinq** chiffres (`imported`, `updated`, `skipped`, et
  les séries du fan-out) et la liste des `failures`. Une série perdue dégrade
  le statut de l'alerte en `warning` : un import où 3 séries sur 12 ont
  échoué ne s'annonce pas en vert. `ImportProgress`, qui savait déjà tout
  afficher mais qu'aucun écran n'importait, a été **supprimé** plutôt que
  remis en service — son rendu était en `ui/` quand l'écran est en `tcn/`.
- Quatre pièges relevés en revue, qui se re-cassent séparément. La garde du
  signalement porte sur l'URL **soumise** (`soumiseRef`), jamais sur l'état
  vivant du champ : corriger son adresse après un échec envoyait sinon un
  `reportPendingProvider` **par frappe**. L'horloge de la minuterie sert aussi
  le décompte du 429, `running` étant déjà `false` quand l'alerte s'affiche —
  sans quoi « Réessayez dans 3 minutes » l'affirmait encore dix minutes plus
  tard. `isDuplicate` teste `!partiel` en tête, faute de quoi un import tout
  en cache **plus** une série perdue affichait « déjà enregistrés » et
  escamotait la liste des manques. Et `failures[].reason` arrive du backend en
  `str(exc)` — anglais, technique, parfois une URL brute : `causeSerie()` le
  traduit en l'une des quatre causes qui changent le geste, le texte d'origine
  restant aux logs.
- Le scrape n'a **rien** à rapporter avant son premier participant : barre
  indéterminée (`.tcn-barre-indeterminee`) **et** minuterie, la seconde
  restant la seule preuve de vie sous `prefers-reduced-motion`, qui fige la
  première. « Annuler l'import » coupe le flux par `AbortController`, et
  `cancel()` lève le verrou sans attendre que le flux veuille bien finir —
  un scrape muet retiendrait sinon le formulaire indéfiniment. Un
  `beforeunload` prévient tant que l'import tourne : fermer l'onglet coupe
  la SSE à mi-course.
- **Une navigation interne, elle, ne coupe rien** (#1062). L'état de
  l'import vit dans `ImportStreamProvider` (monté par `app/providers.tsx`,
  donc au niveau du layout racine), pas dans le formulaire :
  `useImportStream()` lit ce contexte, `useImportStreamController()` en est
  la seule instance. Quitter `/ajouter` démonte `TcnScrapeForm`, la SSE
  continue ; si elle finit sans écran attaché (`attach()`), le provider fait
  ce que l'écran aurait fait (signalement du fournisseur **sur page
  illisible seulement**, `router.refresh()`, télémétrie) et l'annonce par un
  toast global aux mots du bilan (`lib/import-outcome.ts`, partagé avec
  l'écran) : succès nommant l'épreuve et « Voir les résultats », doublon en
  neutre, partiel et échecs persistants (`duration: Infinity`, bouton de
  fermeture), les trois causes de #491 distinctes (délai du 429, service
  muet avec « Relancer l'import », page illisible avec « Saisir à la main »).
  Un échec se dit par sa cause, jamais par le message d'exception, qui porte
  l'anglais du navigateur. Le bilan **reste dans l'état** tant que le toast
  est affiché : revenir sur l'écran le montre en entier (séries perdues,
  « Relancer l'import », saisie manuelle), sans rejouer signalement ni
  rafraîchissement, et referme le toast. Revenir **pendant** l'import remonte
  le formulaire sur le flux ouvert (champ prérempli, barre, horloge lue sur
  `startedAt`, « Annuler l'import ») : le verrou étant global, la même URL
  ne peut pas être relancée tant que le premier flux est ouvert. Le
  `beforeunload` a suivi l'état dans le provider, pour valoir où que l'on
  soit. `ImportStreamProvider.test.tsx` démonte le formulaire en plein
  import et fixe ces comportements.

## Saisie manuelle (#1019)

**La saisie manuelle suit le contrat de `POST /participations`** (#1019) :
`ManualResultForm` vérifie avant l'envoi ce que le serveur refuserait en 422
(temps `H:MM:SS` ou vide, nom et épreuve non vides une fois nettoyés, date
`AAAA-MM-JJ`, place d'au moins 1, statut de la nomenclature, `event_type`
canonique par construction) et n'envoie que des valeurs nettoyées. Un 422
qui passerait quand même arrive rangé par champ (`ApiError.fieldErrors`) et
s'affiche sous le champ concerné, les types génériques de Pydantic traduits
(leur message est anglais), jamais en bloc brut. `TcnScrapeForm` le charge en
`next/dynamic` à l'ouverture de la saisie manuelle (#1395) : il porte zod, seul
module à l'importer, donc aucun import statique de `ManualResultForm.tsx`
(constante comprise) ne doit revenir dans `TcnScrapeForm`.
`TcnScrapeForm.lazy.test.tsx` le tient.

## Le champ URL et son verdict (#492)

**Le champ URL et le verdict qui vit sous lui** (#492) — trois points à ne pas
rouvrir séparément :

- **La taille de police d'un champ TCN vit dans `.tcn-input`, jamais en
  ligne.** 16px sous `md`, 15px au-delà : sous 16px, iOS Safari zoome à la
  mise au point et l'écran fait un bond sur le geste fondateur de l'app. Une
  valeur en ligne rendrait la media query inerte sans que rien ne bronche —
  `app/globals.test.ts` garde les deux crans.
- **Un seul verdict, à un seul endroit.** `ProviderDetector` **est** la ligne
  sous le champ, et ses trois états s'excluent : au repos les chronométreurs
  pris en charge (depuis `useProviders()`, jamais une liste tenue à la main —
  la précédente avait divergé), sinon le fournisseur reconnu ou l'absence de
  reconnaissance avec sa sortie « Saisir à la main ». Le badge rouge et
  l'alerte jaune disaient le même verdict en même temps, pendant que le bouton
  principal restait actif et promettait l'inverse. Sa hauteur est réservée
  (`minHeight`), sans quoi le débounce déplace le bouton pendant la frappe.
- **`providerUnsupported` garde le bouton *et* `submit()`.** Le `disabled` seul
  laisse la touche Entrée lancer l'import que le verdict vient d'exclure.
