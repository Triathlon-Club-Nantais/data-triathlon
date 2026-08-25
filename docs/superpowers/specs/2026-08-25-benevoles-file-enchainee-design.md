# `/benevoles` — file enchaînée et enregistrement unique

- **Issue** : #490 (`PROF-9` + `PROF-10` du § 7 de
  `docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md`)
- **Epic** : #460 — refs #325
- **Voie** : Superpowers (brainstorming → writing-plans → exécution)
- **Date** : 2026-08-25

## Le problème, en une phrase

`/benevoles` est un outil de production interne dont la seule métrique est le
nombre d'entrées traitées à l'heure, et ses deux gestes les plus fréquents sont
ceux qui coûtent le plus : après chaque validation la file se déselectionne
(`PROF-9`), et le panneau demande quatre enregistrements indépendants dont aucun
ne signale qu'on l'a oublié (`PROF-10`).

Les deux entrées vont ensemble : enchaîner la file sans réduire le panneau à un
seul enregistrement laisserait le geste coûteux au milieu de la chaîne.

## Ce que le backend n'a pas à faire

**Aucun changement backend.** `PATCH /benevoles/participations/{id}` passe déjà
`body.model_dump(exclude_unset=True)` à `admin_actions.update_participation_fields`
(`backend/app/api/v1/benevoles.py:231-244`) : un corps partiel ne touche que les
champs envoyés. Les trois routes d'écriture existantes suffisent, et « un seul
enregistrement » est une affaire d'orchestration front.

Écarté explicitement : un endpoint composite `PUT /benevoles/participations/{id}`
qui prendrait nom d'épreuve, champs et réattribution d'un coup. Il ferait
disparaître l'échec partiel côté client au prix d'une route de plus à maintenir
et d'une transaction qui mêle deux agrégats (`Course` et `Participation`) — pour
un écran à public restreint. La simplicité l'emporte (« choisir l'implémentation
la plus simple qui satisfait pleinement le besoin actuel »).

## Découpage

`ParticipationPanel.tsx` fait 393 lignes et porte neuf `useState` indépendants ;
le brouillon unifié l'alourdirait encore. On le casse en unités qui se
comprennent et se testent séparément.

| Fichier | Rôle | Dépend de |
| --- | --- | --- |
| `lib/benevoles/brouillon.ts` | **Pur, sans DOM ni React** : type du brouillon, diff brouillon ↔ `Participation`, plan d'enregistrement, application d'un résultat partiel | `lib/types` |
| `components/benevoles/useBrouillon.ts` | État du formulaire unique, `estSale`, `enregistrer()` | `brouillon.ts`, `apiClient` |
| `components/benevoles/useFileValidation.ts` | Listes file/non conformes, sélection, **passage au suivant**, compteur de session | `lib/types` |
| `components/benevoles/ParticipationPanel.tsx` | Présentation du détail + barre d'action collante | les deux hooks |
| `components/benevoles/ChampsParticipation.tsx` | Les cinq champs éditables + valeurs d'origine | — (présentationnel) |
| `components/benevoles/ReattributionField.tsx` | Recherche d'athlète + choix **différé** | `apiClient` |
| `app/benevoles/page.tsx` | Chargement, garde d'accès, feuille mobile | `useFileValidation` |

**Alternative écartée** : un `useReducer` unique au niveau page portant file *et*
brouillon. Cohérent sur le papier, mais il recouple exactement les deux choses
que l'audit veut séparer, et rend le brouillon intestable sans monter la page
entière.

Chaque unité répond aux trois questions : `brouillon.ts` calcule quoi envoyer et
ne connaît ni React ni le réseau ; `useBrouillon` tient l'état d'un formulaire et
ne connaît pas la file ; `useFileValidation` tient une file et ne connaît pas le
formulaire.

## `PROF-10` — un seul état de formulaire, un seul enregistrement

### Le brouillon

```ts
type Brouillon = {
  nom_epreuve: string;
  bib_number: string;
  rank_overall: string;   // chaîne : le champ est un <input type=number>
  club: string;
  category: string;
  athlete_cible: AthleteBrief | null;  // null = pas de réattribution demandée
};
```

Initialisé depuis la `Participation` sélectionnée. `estSale` est vrai dès qu'un
champ diverge de l'origine ou qu'un `athlete_cible` est choisi.

Chaque champ modifié affiche **sa valeur d'origine à côté de lui** — le
`Participation` complet est déjà en mémoire, rien à recharger. Un champ non
modifié n'affiche rien : la comparaison ne sert qu'à ceux qui ont bougé.

Un bandeau « Modifications non enregistrées » apparaît dès `estSale`.

### La séquence d'enregistrement

`enregistrer()` n'appelle **que ce qui a bougé**, dans un ordre fixe, et
s'arrête au premier échec :

1. `renameCourseBenevole(course.id, nom_epreuve)` — si le nom a changé
2. `updateParticipationFieldsBenevole(id, champs)` — les quatre champs modifiés,
   en un seul `PATCH` partiel
3. `reassignParticipationBenevole(id, athlete_cible.id)` — si un athlète a été
   choisi

L'ordre n'est pas arbitraire : le renommage porte sur la `Course` et non sur la
`Participation`, donc les réponses des étapes 2 et 3 rendent déjà le nom
corrigé ; et la réattribution est mise en dernier parce que c'est le seul geste
qui change de quel athlète on parle — la placer avant ferait porter une
correction de dossard sur une identité déjà déplacée si l'étape suivante échoue.

L'état final de la participation est la **dernière réponse `Participation`
obtenue** ; si seule l'étape 1 a tourné, c'est `{ ...participation, course }`.

### L'échec partiel

C'est le point délicat, et il est réel : les trois routes peuvent rendre 409
(collision de nom d'épreuve, dossard en doublon, réattribution en conflit) — les
trois cas sont déjà couverts par les tests actuels de `ParticipationPanel`.

Ce qui est passé est commité côté serveur. Donc :

- on **rebase le brouillon sur les réponses obtenues** : les champs enregistrés
  cessent d'être sales, leur valeur d'origine devient la nouvelle valeur ;
- ne reste sale que ce qui n'a pas pu partir ;
- le message d'erreur **nomme l'étape** en français : « Le nom de l'épreuve n'a
  pas pu être enregistré : une autre épreuve porte déjà ce nom. » — une zone
  d'erreur unique, pas quatre ;
- la validation **ne part pas** si un enregistrement a échoué.

### La validation enregistre d'abord

« Valider ce résultat » exécute `enregistrer()` si `estSale`, puis
`validateParticipationBenevole`. C'est ce qui ferme le trou décrit par `PROF-10` :
un dossard saisi sans avoir cliqué le bon bouton n'est plus emporté en silence.

Si l'enregistrement échoue, la validation est abandonnée et l'erreur reste à
l'écran — l'entrée n'est ni validée ni retirée de la file.

### La barre d'action collante

« Valider ce résultat », « Signaler non conforme » et « Enregistrer » vivent dans
une barre collante en bas du panneau (`position: sticky; bottom: 0`), sur le
chemin de lecture et jamais hors écran. L'action primaire est unique et
visuellement dominante ; le rejet reste secondaire et garde sa confirmation en
deux temps.

### Le cas rejeté

Une entrée rejetée reste en lecture seule, avec « Annuler le rejet » pour seule
action — comportement actuel conservé. Le brouillon n'est pas éditable tant que
le rejet n'est pas levé.

## `PROF-9` — la file s'enchaîne

### Le passage au suivant

`useFileValidation` remplace le `setSelectedId(null)` de `page.tsx:52-55`. Après
une validation ou un rejet, l'entrée retirée libère un index : on sélectionne
**celle qui prend sa place**, à défaut la précédente, à défaut rien (file vide).

Conséquence : `selectedId === null` avec une file non vide devient un état
impossible. L'écran « Sélectionnez un résultat dans la file pour le relire » ne
sert plus qu'au tout premier affichage.

### Le retour d'information

- Toast sonner (`Toaster` déjà monté dans `app/layout.tsx:90`) :
  « Résultat validé — 12 restants. »
- Doublé d'une `AnnonceStatut` (`components/tcn/AnnonceStatut.tsx`) : le toast
  seul ne satisfait pas WCAG 4.1.3, et c'est le patron déjà retenu dans ce dépôt
  pour les décomptes qui changent sans déplacer le focus.
- **Compteur de session** à côté des onglets : « 7 traités ». Il compte les
  validations et les rejets de la session courante, repart à zéro au
  rechargement, et n'est pas persisté — c'est un encouragement, pas une donnée.

### L'état vide devient un état de réussite

La file réellement épuisée n'affiche plus « Aucun résultat en attente de
validation » mais un état de réussite (« File vide, merci ! »). L'onglet
« Non conformes » garde son état vide neutre : y arriver n'est pas un
accomplissement.

### Le garde-fou du brouillon sale

Changer d'entrée — à la main ou par enchaînement — en laissant des modifications
non enregistrées demande **confirmation**. Sans lui, l'enchaînement automatique
deviendrait lui-même une nouvelle source de perte de saisie silencieuse, soit
exactement le défaut que `PROF-10` corrige.

## Mobile

Sous le point de rupture `md`, le panneau n'est plus rendu sous la file : il
s'ouvre en **feuille** (`SheetContent side="right"`), sur le patron déjà en place
dans `AppNav.tsx:352-377`. On récupère gratuitement le déplacement du focus, la
fermeture par `Escape` et le retour arrière — les trois manques relevés par
`PROF-9` sur `ValidationQueue.tsx:62`.

Au-dessus de `md`, la grille deux colonnes
`md:grid-cols-[minmax(280px,360px)_1fr]` reste inchangée : le panneau est déjà à
côté de la file, une feuille n'y apporterait rien.

La barre d'action collante vit en bas de la feuille sur mobile, en bas du panneau
sur desktop — même composant, même position relative au conteneur.

## Tests (TDD, dans cet ordre)

Le TDD est non négociable (Principe III de la constitution). L'ordre suit les
dépendances, du pur vers le monté :

1. **`lib/benevoles/brouillon.ts`** — unitaire pur, sans DOM :
   - un brouillon identique à l'origine ne produit aucun appel ;
   - seuls les champs modifiés entrent dans le `PATCH` ;
   - le plan respecte l'ordre renommage → champs → réattribution ;
   - l'application d'un résultat partiel rebase les champs passés et ne garde
     sales que les autres.
2. **`useFileValidation`** — la validation sélectionne la suivante ; la dernière
   entrée validée laisse la file vide ; un rejet fait passer l'entrée dans l'autre
   onglet et sélectionne la suivante ; le compteur avance sur validation et sur
   rejet.
3. **`useBrouillon`** — `estSale`, l'enregistrement partiel, la validation qui
   enregistre d'abord, la validation abandonnée sur échec d'enregistrement.
4. **Composants** — `ChampsParticipation` affiche la valeur d'origine des seuls
   champs modifiés ; `ReattributionField` choisit sans écrire ; le panneau rend
   une zone d'erreur unique ; la feuille s'ouvre sous `md`.

**Les tests existants de `ParticipationPanel` qui assertent les quatre boutons
séparés sont réécrits, pas conservés.** La compatibilité ascendante ne se
préserve pas ici : « Enregistrer le nom » et « Enregistrer les modifications »
disparaissent, et un test qui les cherche encore décrirait un écran qui n'existe
plus. Les tests de conflit 409 (nom, dossard, réattribution), eux, survivent —
leur assertion change de cible, pas de sens.

## Hors périmètre

- **Raccourcis clavier** — suggérés par `PROF-9`, absents de l'« Attendu » de
  #490. Ils ouvrent leur propre surface d'accessibilité (ne pas se déclencher
  pendant la saisie, être découvrables) et méritent leur lot.
- **Cibles tactiles des onglets de file** — lot `CIBLE-1`, dépendance nommée par
  l'issue.
- **Comparaison avec ce que la source annonçait** — évoqué dans le corps de
  `PROF-10`, non repris dans l'« Attendu ».
- **Identité visuelle** (`--tcn-*`, Anton/Barlow) et frontière
  `components/tcn/` ↔ `components/ui/` — arbitrées, non rejugées (#460, #325).
