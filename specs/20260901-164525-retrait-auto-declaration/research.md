# Research: Retrait de l'auto-déclaration de bénévolat (#816)

## D1 — Retrait complet, pas seulement de l'affichage

**Décision** : retirer, dans l'ordre de dépendance, les composants
frontend, les routes, les fonctions de service, les fonctions repository et
les pouvoirs `benevolat:read`/`benevolat:manage` du domaine
`VolunteerDeclaration` (#751).

**Rationale** : même raisonnement que #780 pour l'ancien geste admin de
l'epic #776 — `test_permissions_catalogue.py::
test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource` fait
échouer la suite si un pouvoir reste dans le catalogue sans aucune route
qui le garde. `FEATURE_VOLUNTEERING` (`permissions.py:45`) devient
également orpheline — aucun autre pouvoir ne l'utilise après le retrait de
`BENEVOLAT_READ`/`BENEVOLAT_MANAGE` — et se retire avec eux.

## D2 — Suppression de table, pas de conservation de données

**Décision** : `VolunteerDeclaration` (table + modèle) est retirée par une
migration Alembic (`op.drop_table`), sans étape de conservation ou de
migration des lignes existantes vers `VolunteerAction`.

**Rationale** : aucune demande de rétention n'a été formulée (spec.md
Assumptions), et les deux tables ne partagent pas de schéma compatible —
`VolunteerDeclaration` n'a pas de rattachement à un athlète, `VolunteerAction`
l'exige. Une migration de données inventerait une correspondance qui n'a
jamais existé.

## D3 — `/admin/benevolat` livrée avec #817, pas seule

**Décision** : cette sous-issue et #817 (écran de validation admin des
déclarations de crédit d'athlète) sont implémentées dans la même fenêtre de
travail, avant toute fusion vers une branche partagée au-delà du worktree de
travail — décision produit explicite (AskUserQuestion), capturée dans
spec.md Edge Cases/Assumptions.

**Rationale** : sans cela, `/admin/benevolat` traverserait un état vide (ou
une 404) entre le retrait de l'ancien contenu et la livraison du nouveau —
un intermédiaire jamais acceptable en production. Exécution : #816 est
implémentée dans ce worktree, puis #817 y est enchaînée avant tout push
vers une branche partageable, pour qu'aucun commit poussé ne laisse la
route cassée.

## D4 — `nav.config.ts` : deux entrées à retirer, aucune à garder

**Décision** : l'entrée admin réelle (`id: "a-benevolat"`, ligne 215-221,
gardée par `benevolat:read`, devenu inexistant) et l'entrée orpheline
(ligne 265, même id, `soon: true`, jamais rendue — relevée dans #814) sont
toutes deux retirées par cette sous-issue.

**Rationale** : la première perd son pouvoir de garde, elle doit disparaître
avec lui. La seconde est un doublon d'id mort depuis l'origine (avant même
ce retrait) — #817 posera sa propre entrée, avec un id distinct, pour
l'écran de validation qu'elle construit.

## D5 — Commentaires croisés à corriger, pas à laisser pourrir

**Décision** : les commentaires qui nomment `volunteer_declarations.py`/
`test_admin_volunteer_declarations_api.py` comme « patron » dans
`volunteer_actions.py`/`test_admin_volunteer_actions_api.py` sont mis à
jour ou retirés une fois ces fichiers supprimés.

**Rationale** : un commentaire qui renvoie vers un fichier supprimé induit
en erreur le prochain lecteur — coût de correction nul au moment du
retrait, coût de découverte non nul plus tard.
