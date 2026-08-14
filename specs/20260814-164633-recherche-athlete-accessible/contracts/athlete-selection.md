# Contrat interne — sélection d'athlète retenue

Pas d'API HTTP concernée : ce contrat est **interne au front**, entre le
module de stockage (`frontend/components/layout/AthletePicker.tsx`) et ses
deux consommateurs (`AppNav`, et le nouveau `SelectAthleteButton` de la page
profil). Il fige la forme que ces deux consommateurs peuvent supposer stable.

## Stockage

- **Clé** : `localStorage["tcn-athlete"]` (inchangée).
- **Valeur** : `JSON.stringify(PickedAthlete)` où
  `PickedAthlete = { id: number; prenom: string; nom: string }` (inchangé).
- **Absence de valeur / valeur invalide** : équivaut à "aucun athlète
  retenu" — jamais d'exception levée côté lecteur.

## Fonctions exportées (`AthletePicker.tsx`)

| Fonction | Signature | Effet |
|---|---|---|
| `readAthlete` | `() => PickedAthlete \| null` | Lecture défensive, inchangée. |
| `writeAthlete` | `(a: PickedAthlete) => void` | Écrit la sélection, **émet l'événement de sync** (nouveau). |
| `clearAthlete` | `() => void` | **Nouveau.** Supprime la clé, émet l'événement de sync. |

## Événement de synchronisation

- **Nom** : `"tcn-athlete-changed"`.
- **Émetteur** : `window.dispatchEvent(new Event("tcn-athlete-changed"))`,
  déclenché par `writeAthlete` et `clearAthlete` après écriture effective du
  `localStorage` (donc pas si l'écriture échoue silencieusement, ex. mode
  privé — cf. gestion d'erreur existante).
- **Payload** : aucun — les abonnés relisent l'état via `readAthlete()`, pour
  n'avoir qu'une seule source de vérité (le storage lui-même, jamais
  l'événement).
- **Abonné** : `AppNav`, en plus de sa lecture au montage.
- **Portée** : même onglet uniquement (un `CustomEvent`/`Event` sur `window`
  ne traverse pas les onglets — contrairement à l'événement `storage` natif,
  qui lui ne se déclenche jamais dans l'onglet émetteur). Un autre onglet
  ouvert sur l'app ne se synchronise qu'à son prochain montage/rechargement —
  hors périmètre de cette feature (non demandé par l'issue #323).
