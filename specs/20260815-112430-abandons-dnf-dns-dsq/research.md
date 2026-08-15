# Phase 0 — Research

Aucun `NEEDS CLARIFICATION` dans le Technical Context : la décision produit
(option B, additive, après #322) était déjà tranchée en amont de la spec.
Ce document consigne les décisions de conception plus fines, pas encore
tranchées par l'issue elle-même.

## Décision : `non_finishers` reste calculé indépendamment, pas dérivé de `dnf+dns+dsq` côté schéma

**Decision** : `stats_service.course_summary` continue de calculer
`non_finishers` en incrémentant le même compteur qu'aujourd'hui à chaque statut
de `_STATUTS_NON_FINISHERS`, et incrémente en parallèle `dnf`, `dns` ou `dsq`
selon le statut exact. `non_finishers` n'est pas recalculé à partir des trois
nouveaux champs a posteriori.

**Rationale** : les deux proviennent de la même boucle sur les mêmes lignes ;
calculer les quatre valeurs en un seul passage évite un second passage ou une
étape de dérivation, et garde `non_finishers == dnf + dns + dsq` vrai par
construction plutôt que par un test qui recalculerait la même chose deux fois.

**Alternatives considered** : dériver `non_finishers` en propriété Pydantic
`(dnf + dns + dsq)` sur `CourseSummary` — rejeté : `non_finishers` est déjà un
champ simple consommé tel quel par le front (Principe IV, contrat existant) ;
introduire une propriété calculée ajoute une indirection pour un gain nul, le
calcul actuel étant déjà correct.

## Décision : libellés français des trois pastilles

**Decision** : « Abandons » (inchangé, `DNF`), « Non-partants » (`DNS`),
« Disqualifiés » (`DSQ`).

**Rationale** : ce sont les termes déjà employés dans l'issue #331 et dans les
commentaires existants du code (`backend/app/services/stats_service.py:145`,
`backend/app/scrapers/raceresult.py:850` — « Non Partants »), donc aucun
nouveau vocabulaire à faire accepter aux bénévoles ou aux visiteurs.

**Alternatives considered** : « DNF/DNS/DSQ » bruts — rejeté, jargon fédéral
peu lisible pour un visiteur non initié (Principe I : français pour le
visible utilisateur).

## Décision : même distinction dans `resumeEpreuve` (`RaceFinishers.tsx`) que dans les `MetaPill` de la page

**Decision** : les deux sites de rendu affichent les mêmes trois catégories
avec les mêmes conditions de masquage (rien si nul), plutôt que de laisser
`RaceFinishers` répéter le mot générique « abandons ».

**Rationale** : la spec (US2) exige la cohérence entre les deux affichages du
même agrégat sur la même page ; laisser diverger l'un des deux reproduirait
exactement le défaut que corrige US1, ailleurs sur l'écran.

**Alternatives considered** : ne toucher que la page principale (`page.tsx`)
et laisser `RaceFinishers` inchangé — rejeté, explicitement exclu par
l'US2 de la spec.
