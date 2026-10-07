# Plan : fournisseur nextrun.fr (#1224)

Source de vérité : `docs/superpowers/specs/2026-10-06-nextrun-altichrono-sondage.md`,
complété des mesures du 07/10 consignées dans `docs/scrapers/nextrun.md`.

## Décisions

- Provider sans fan-out : une ligne `ModuleProvider("nextrun", ("nextrun.fr",), nextrun)`.
- Une ligne par personne sur les duos, comme runnerbreizh (seul fournisseur qui publie
  déjà un duo équipier par équipier) : chaque équipier a son dossard, son temps, son
  sexe, sa catégorie et son rang, donc ni collision de dossard ni rang dupliqué.
  Le découpage de #895 / la liaison de #997 ne s'appliquent pas : rien à découper.
- « Licence Expérience » n'est pas un club (type de licence, 177 lignes sur 306) : club vide.
- Courses `results_published: false` ignorées ; pagination par `page`, `page_size=200`
  (valeurs admises : 20, 50, 100, 200).

## Tâches (TDD)

1. Tests réseau coupé sur fixtures Lancieux 2026 (édition, duo XS, solo XS en deux pages),
   puis `backend/app/scrapers/nextrun.py`.
2. Registre : `PROVIDERS`, tests de routage et de jetons de host.
3. Test `integration` sur l'URL réelle (`LIVE_URLS`).
4. Docs : `docs/scrapers/nextrun.md`, `scrapers/AGENTS.md`, décision #332, compte des
   fournisseurs ; front : `PROVIDER_LABELS`, politique de confidentialité (`updatedAt`).
