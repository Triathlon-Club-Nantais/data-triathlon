# Détection et stockage du relais par participation (TimePulse)

Date : 2026-06-15
Cible : `backend-v2/`, `frontend-v2/`

## Problème

Sur TimePulse (ex. « LE NORTH MAY », épreuve 3232), une même épreuve mélange des
participants **solo** et des équipes de **relais**. Impossible aujourd'hui de
distinguer les deux : on ne voit pas et on ne stocke pas l'information.

Constats :

- `ScrapedResult.is_relay` existe mais le scraper TimePulse ne le renseigne
  **jamais** (toujours `False`).
- `is_relay` n'existe que sur le modèle `Course`, pas sur `Participation`.
- Le classifieur ramène « Triathlon L RELAIS » et « Triathlon L SOLO » au même
  `event_type` (`triathlon-l`). Comme une Course est identifiée par
  `(name, event_date, event_type)`, **solo et relais fusionnent dans la même
  Course** → un flag au niveau Course est inadapté pour TimePulse.

Bonne nouvelle : les classements sont calculés par parcours `p`, donc solos et
relais ne sont pas mélangés au classement.

## Détection du relais (TimePulse)

Deux marqueurs concordants dans le XML :

- Parcours `p` contient « RELAIS » (vs « SOLO ») — ex. `p="Triathlon L RELAIS"`.
- Catégorie `ca ∈ {EQX, EQM, EQF}` (équipe mixte / hommes / femmes).

Règle : `is_relay = "relais" in p.lower() OR ca in {"EQX","EQM","EQF"}`.

## Décision d'architecture

Le relais devient une propriété **par participation**, pas par course.
`course.is_relay` est conservé tel quel : il garde son sens pour les providers où
tout le heat est un relais (Wiclax/Breizh, courses dédiées). Pour TimePulse
(course mixte), il reste best-effort ; la vérité est portée par la participation.

## Changements — Backend-v2

1. **Scraper** `app/scrapers/timepulse.py` : helper `_is_relay(parcours, category)`
   appelé dans `scrape_event_all`, renseigne `result.is_relay`.
2. **Modèle** `app/models/participation.py` : colonne `is_relay: bool = False`.
3. **Migration Alembic** `add_participation_is_relay` (server_default `false`).
4. **Mapping** `app/services/mapping.py` : `participation_fields` ajoute
   `"is_relay": scraped.is_relay`.
5. **Schéma** `app/schemas/participation.py` : `ParticipationOut.is_relay: bool = False`.

## Changements — Frontend-v2

- `lib/types.ts` : ajouter `is_relay` au type miroir de `ParticipationOut`.
- `components/results/ResultCard.tsx` : le badge « Relais » lit `result.is_relay`
  avec repli `|| course.is_relay`. Mise à jour de la fixture du test.

## Tests

- TimePulse : un cas relais (`p` « RELAIS » + `ca="EQX"`) → `is_relay True` ;
  un solo → `False`.
- Mapping : `participation_fields` propage `is_relay`.

## Seed

Aucun changement : `seed_demo.py` scrape en live via `import_event`. Après la
correction, `task bv2:reset-db` repeuple `is_relay` correctement.

## Hors périmètre

Les relais créent des `Athlete` au nommage bancal
(« CANNIOU/OLIVIER Cedric/Leclerc »). Modéliser proprement les équipiers est un
autre chantier, non traité ici.
