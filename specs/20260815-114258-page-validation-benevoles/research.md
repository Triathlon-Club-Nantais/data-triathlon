# Research: Page de vérification des résultats par les bénévoles

Phase 0 du plan — décisions techniques prises pour lever les inconnues du
Technical Context, chacune avec l'alternative rejetée.

## D1 — Mécanisme d'accès : cookie signé sans nouvelle table

**Décision** : un unique secret d'environnement (`BENEVOLE_SHARED_PASSWORD` ou
équivalent, à nommer en cohérence avec `core/config.py`) protège un endpoint de
connexion. À la vérification (`hmac.compare_digest`, stdlib — jamais `==` sur
un mot de passe), le serveur pose un cookie de session **signé par HMAC-SHA256
avec le mot de passe lui-même comme clé** : `{horodatage}.{HMAC(clé=mot de
passe, message=horodatage)}`. La vérification recalcule ce HMAC à chaque
requête avec le mot de passe **courant** lu depuis la configuration. Cookie de
session (sans `Max-Age`) : il s'efface à la fermeture du navigateur, conforme à
l'hypothèse actée en spec (§ Assumptions) faute d'exigence de durée dans
l'issue.

**Rationale** :
- **Aucune nouvelle table.** La révocation individuelle n'a pas de sens ici —
  il n'y a pas d'identité individuelle à révoquer (c'est tout le point du choix
  RGPD/CNIL déjà arbitré, cf. spec § Décisions actées) — et la révocation
  *collective* (rotation du mot de passe) invalide automatiquement tous les
  cookies existants, puisque la clé de vérification change avec lui. C'est
  exactement le même compromis que celui déjà noté sur #169 dans l'issue
  (« sans identité individuelle ni révocation ») — accepté ici en connaissance
  de cause, pas ignoré.
- **Aucune primitive cryptographique réinventée** : `hmac`/`hashlib`/`secrets`
  sont stdlib, déjà le socle du jeton opaque de session SSO
  (`services/auth/session.py`). Pas de nouvelle dépendance.
- **Isolation du socle SSO** : ce mécanisme ne touche ni `users`, ni
  `identities`, ni `user_sessions`, ni `allowed_emails` — les quatre tables du
  socle #114/#170 restent celles du SSO individuel, pas mêlées à un accès
  partagé qui n'a pas les mêmes garanties d'identité.

**Alternatives rejetées** :
- *Rôle RBAC individuel via `/admin/droits`* (proposé dans le dernier
  commentaire de l'issue) — cohérent avec l'infrastructure existante, mais
  **rouvrirait une décision produit déjà actée pour ce cadrage** (mot de passe
  partagé, cf. spec § Décisions actées) ; non retenu ici, documenté comme
  tension non résolue plutôt que tranché unilatéralement.
- *Table de sessions bénévoles dédiée* (jeton opaque, empreinte en base, sur le
  patron exact de `services/auth/session.py`) — assurerait une révocation fine,
  mais introduirait une table entière et un point d'écriture supplémentaire
  pour un besoin que la rotation du mot de passe couvre déjà. Rejetée par le
  principe VI (simplicité/YAGNI) : la table achèterait une capacité
  (révocation d'un seul cookie) qu'aucune exigence de la spec ne demande.
- *Basic Auth HTTP* — plus simple encore, mais expose le mot de passe à chaque
  requête (pas de logout propre, pas de contrôle du cookie côté front,
  ergonomie de saisie native du navigateur peu adaptée à un écran applicatif).
  Rejetée pour l'expérience utilisateur, pas pour la sécurité.

## D2 — Attribution des écritures dans le journal d'audit : compte système générique

**Décision** : une ligne unique dans `users` (aucune ligne `identities`
associée — elle ne se connecte jamais par OAuth), nommée de façon
reconnaissable (ex. « Bénévoles (accès partagé) »), sert de `user_id` à toute
écriture déclenchée depuis la page bénévoles vers `admin_action_log_repository`.

**Rationale** : `AdminActionLog.user_id` est une **FK NOT NULL** vers `users`
(cf. `backend/app/models/admin_action_log.py` : « l'auteur ne disparaît pas »).
Les deux gestes de renommage d'épreuve et de réattribution d'athlète
**réutilisent déjà** `services/admin_actions.update_course` et
`.reassign_participation`, qui exigent tous deux un `user_id`. Sans compte
générique, il faudrait soit rendre la colonne nullable (touche un invariant du
socle #115 partagé avec tous les écrans `/admin/*`, hors périmètre de cette
feature), soit dupliquer la logique métier de ces deux fonctions sans
journalisation (perd la traçabilité que le reste du back-office a
systématiquement). C'est aussi l'option que le porteur produit envisageait
lui-même dans l'issue (13/08 16:28) : « on pourrait tricher en disant que c'est
un user générique qui possède des droits ». Un compte système n'est pas une
identité individuelle : il ne s'authentifie jamais, ne se connecte jamais, ne
collecte aucune donnée personnelle — la contrainte RGPD/CNIL qui a motivé le
choix du mot de passe partagé reste respectée.

**Alternatives rejetées** :
- *`user_id` nullable sur `AdminActionLog`* — touche une contrainte du socle
  RBAC (#115) partagée par six autres routers `admin_*`, pour un besoin propre
  à cette seule feature. Rejetée : blast radius disproportionné.
- *Pas de journalisation pour les actions bénévoles* — cohérent avec « pas
  d'identité individuelle », mais romprait la garantie que **toute** écriture
  d'administration est tracée, déjà posée par #117/#118 pour six ressources.
  Rejetée : une trace « acte par le compte générique bénévoles » reste un
  signal utile (quoi, quand, sur quelle entité), même sans distinguer lequel
  des 5-6 bénévoles a agi.

## D3 — Bibliothèque de composants front : `components/ui/` composé avec `components/tcn/`

**Décision** : l'écran (file de résultats à gauche, panneau de correction et
de validation à droite) utilise les primitives denses de `components/ui/`
(table ou liste, dialog/sheet, select) pour la structure d'interaction, et
compose des éléments `components/tcn/` (Card, badges de statut) pour l'identité
visuelle des blocs d'information. Le fichier `.dc.html` joint à l'issue reste
une inspiration de layout, jamais un composant porté tel quel.

**Rationale** : `frontend/AGENTS.md` réserve `ui/` aux écrans qui « ont besoin
de [la] densité » des primitives complexes — une file de validation avec
panneau d'édition à deux colonnes en est un exemple typique, structurellement
proche des écrans `/admin/*` qui l'utilisent déjà. La frontière documentée
n'est cependant pas tracée sur l'authentification (SSO vs mot de passe) mais
sur la **densité d'écran** : cette page n'est pas sous `/admin/*`, mais sa
densité d'interaction (liste + panneau + formulaires d'édition) est la même.
Composer les deux bibliothèques est déjà le motif attendu ailleurs (`AppNav`
avec `ui/sheet` + `tcn/Avatar`, `EventList` avec `ui/select` + `tcn/Card`) —
ce n'est pas un mélange à arbitrer au cas par cas, c'est la règle telle
qu'écrite.

**Statut** : décision **prise sur preuve documentée**, pas par défaut — mais à
confirmer une fois l'écran maquetté si sa densité réelle s'avère plus proche
d'un écran public que d'un écran back-office.

**Alternatives rejetées** :
- *`components/tcn/` seul*, tel qu'évoqué dans le brief initial de ce cadrage —
  cohérent avec « accès hors `/admin/*` », mais contredit la frontière
  documentée par `frontend/AGENTS.md`, qui trace la limite sur la densité
  d'écran et non sur le mécanisme d'authentification.

## D4 — Lecture de la file : réutilisation de `core/validation.validated_clause`

**Décision** : la requête de file (geste 1) filtre
`Participation.is_pending_validation.is_(True)` — le complément exact de
`validated_clause`, déjà posé par #270 dans `core/validation.py` sur le patron
de `core/club.is_tcn`/`tcn_clause`. Aucun nouveau prédicat n'est introduit ; si
un besoin de clause SQL composée apparaît au moment des tâches, il complète ce
module plutôt que d'en dupliquer la logique ailleurs.

**Rationale** : `core/validation.py` documente explicitement l'intention de ce
module — « un prédicat Python et une clause SQL qui partagent la même règle »,
pour la même raison que #76 a motivé `core/club.py`. Une seconde
implémentation du filtre « en attente » dans `participation_repository`
romprait cette garantie dès la première feature qui en a besoin.

## D5 — Portée de la file : tous clubs confondus, pas de filtre `scope`

**Décision** : la file de validation ne filtre **pas** par club ou par portée
(`scope`, `federal_only`) — elle montre tous les résultats en attente, quel
que soit le club du déclarant.

**Rationale** : les bénévoles valident les saisies de **leurs propres**
membres ; restreindre la file par club dupliquerait une notion (`tcn_clause`)
sans qu'aucune exigence de la spec ne la demande, et introduirait une surface
où le Principe V (neutralité par défaut des paramètres transverses)
s'appliquerait pour rien. Rejeté par simplicité : ajouter un filtre sans besoin
exprimé est l'abstraction spéculative que le Principe VI proscrit.
