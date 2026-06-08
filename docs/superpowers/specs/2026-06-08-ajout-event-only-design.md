# Refonte du formulaire d'ajout en flux « event-only » (frontend-v2)

Date : 2026-06-08
Cible : `frontend-v2/`

## Contexte

Le formulaire d'ajout (`ScrapeForm`) conserve un étage de prévisualisation
athlète-unique hérité du frontend v1 : champ « Dossard », bouton « Analyser »,
carte « Vérification » avec `PreviewEditor`. Cet étage repose sur
`apiClient.scrape(url, bib)` → `POST /api/v1/scrape`.

**Ce endpoint n'existe pas dans backend-v2.** Le router scrape n'expose que
`POST /scrape/event`, `POST /scrape/event/stream`, `GET /scrape/detect`. La
décision d'architecture « scraping = épreuve seule » a supprimé le scraping
athlète-unique côté backend.

**Conséquence actuelle** : sur backend-v2, le bouton « Analyser » appelle un
endpoint 404 → le `catch` se déclenche systématiquement → bascule en saisie
manuelle **et** signale l'URL comme provider non supporté. L'étape de
prévisualisation ne fonctionne jamais.

Le champ « Dossard » de l'étape 1 ne sert qu'à alimenter cet appel mort : il
n'a plus d'utilité. C'est le symptôme d'un étage de preview entièrement obsolète
contre backend-v2.

## Objectif

Aligner le formulaire d'ajout sur le flux event-only de backend-v2 : coller une
URL → importer directement tous les participants de l'épreuve (SSE). Supprimer
l'étage de prévisualisation athlète-unique. Conserver la saisie manuelle comme
fallback pour les fournisseurs non supportés.

## Design

### Flux `ScrapeForm`

**Étape 1 — Source**
- Input URL + `ProviderDetector` (inchangé : badge « Fournisseur : klikego » ou
  « Non supporté (...) — saisie manuelle »).
- Deux actions :
  - **« Importer l'épreuve »** (primaire) → `importStream.start(url)` directement
    (SSE), sans preview intermédiaire. Désactivé tant que l'URL est vide ou
    qu'un import est en cours.
  - **« Saisie manuelle »** (outline) → ouvre `ManualResultForm`.

**Étape 2 — Saisie manuelle** (uniquement si activée)
- `ManualResultForm` inchangé → `saveParticipation` (`POST /participations`).
- Garde son propre champ « Dossard » : ici c'est une donnée du résultat saisi,
  pas un paramètre de scrape — donc légitime.

**Progression** : `ImportProgress` sous le formulaire (inchangé), piloté par
`useImportStream`.

### Gestion d'erreur (option A)

`ProviderDetector` détecte déjà le non-supporté en amont (badge rouge). Le report
« provider non supporté » se fait **à l'échec réel du flux d'import** :
- Si `importStream` se termine en erreur → toast d'erreur, `reportPendingProvider(url)`,
  et invitation à utiliser la saisie manuelle (`setManual(true)`).
- On ne signale pas tant que l'utilisateur n'a pas tenté d'import.

### Suppressions

- État `bib` + input « Dossard » de l'étape 1.
- État `preview` + composant `PreviewEditor` + carte « Vérification ».
- Callback `scrape()` (remplacé par `importStream.start(url)`).
- Méthode `apiClient.scrape()` dans `lib/api/client.ts` (morte).
- Report de provider dans l'ancien `catch` du scrape unique (déplacé sur l'échec
  d'import, cf. option A).

### Conservé

`ProviderDetector`, `ManualResultForm`, `ImportProgress`, `useImportStream`,
`useSaveParticipation`, `apiClient.reportPendingProvider`,
`apiClient.importEvent` / le stream SSE.

## Impacts

- `frontend-v2/components/scrape/ScrapeForm.tsx` — réécriture du flux.
- `frontend-v2/lib/api/client.ts` — suppression de `scrape()`.
- Aucun test existant ne couvre ce chemin. Ajouter une couverture sur le nouveau
  comportement (import direct + bascule manuelle sur erreur) est souhaitable.
- `app/ajouter/page.tsx` — la description mentionne « Le résultat de l'athlète est
  prévisualisé » : à reformuler en cohérence avec le flux event-only.

## Hors périmètre

- Pas de modification backend (la décision event-only est conservée, on ne
  restaure pas `/scrape`).
- Pas de refonte de `ManualResultForm` ni de `ImportProgress`.
