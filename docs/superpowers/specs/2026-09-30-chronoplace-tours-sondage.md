# Sondage Chronoplace : épreuves au nombre de tours (#993)

Sondé le 30/09/2026 sur les pages en direct, `GET ?perPage=all`.

## Préalable : le markup avait changé

Sur les deux épreuves, le scraper rendait **0 participant** : `wire:click="sortBy('<clé>')"`
a glissé du `<th>` vers le `<button>` qu'il contient, et la page porte une seconde
table (vue étroite). Les tests d'intégration Chronoplace échouaient (2 sur 5).
Corrigé dans le même lot : la clé se lit sur le `<th>` ou sur son bouton.

## La source ne dit pas le format

Le snapshot Livewire du composant `classement-table` porte les mêmes clés sur les
deux épreuves (`affichageDonnees.nb_tours: true`, `portee: "ETAPE"`, rien sur une
durée ni un nombre de tours attendu). La page n'en dit pas plus : « Nb Tours »,
« Tours », « Détails des tours ». Le format se lit donc **dans les données**.

## Mesures

| Épreuve | Lignes | Tours | Part au maximum | Temps (min → max) | Écart relatif des temps |
| --- | --- | --- | --- | --- | --- |
| SwimRun Spay'cific 2025 (566), durée fixe | 41 | 9 à 15 | 5 % (2 à 15 tours) | 02:00:20 → 02:12:03 | 9 % |
| 24 h VTT (493, fixture), durée fixe | 2 | 88 et 95 | 50 % | 23:59:53 → 24:00:13 | 0 % |
| Vétathlon de la Colmont 2025 (551), tours fixés | 53 | 50 à 9, 2 à 5, 1 à 1 | 94 % | 00:10:50 → 01:56:07 | 91 % |

Sur 566, chaque nombre de tours couvre toute la plage de temps (10 tours : 7226 s
à 7495 s ; 15 tours : 7220 s à 7537 s) : le temps ne classe rien. Sur 551, les
lignes sous 9 tours sont les plus rapides (1 tour en 00:10:50) : ce sont des
abandons, le seul signal qu'en publie la source.

## Règle retenue

Sur une épreuve dont les tours **varient** :

- **Durée fixe** si l'écart relatif des temps, `(max − min) / max`, reste sous
  **20 %** : tout le monde est arrêté à la même heure. L'épreuve est marquée
  `ranked_by_laps` (colonne `courses.ranked_by_laps`), et sort de l'histogramme des
  temps et de la comparaison aux positions de référence. Personne n'y abandonne
  par défaut.
- **Tours fixés** sinon : une ligne sous le maximum de tours de l'épreuve devient
  `DNF`, sans temps ni rang.

Le seuil laisse de la marge des deux côtés (9 % et 0 % contre 91 %). Une épreuve à
tours fixés sans abandon a tous ses tours égaux : elle reste une épreuve
ordinaire.

## À faire en production

Re-scraper les courses 157 et 158 (566) une fois le correctif livré : elles
passent `ranked_by_laps`. Suivi dans #1009.
