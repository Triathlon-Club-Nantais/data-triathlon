# Research: Bouton de signalement (bug / feedback)

## D1 — Limitation de débit anti-spam : requête de comptage, pas de dépendance nouvelle

**Decision**: la limitation par IP se fait par une requête de comptage sur la
table `user_feedback` elle-même (`COUNT(*) WHERE ip_address = ? AND created_at
> now() - fenêtre`), exécutée dans `feedback_repository.count_recent_by_ip`
avant chaque insertion. Seuil et fenêtre sont deux réglages (`FEEDBACK_
RATE_LIMIT_MAX_PER_WINDOW`, `FEEDBACK_RATE_LIMIT_WINDOW_SECONDS`), au même
endroit que les autres constantes métier de `core/config.py`
(`geocode_min_interval_seconds`, `cache_ttl_*`).

**Rationale**: aucune dépendance de rate-limiting (`slowapi`, `fastapi-
limiter`…) n'existe déjà dans `backend/pyproject.toml`. Le dépôt n'en a jamais
eu besoin (endpoints publics jusqu'ici en écriture faible fréquence :
`pending-providers`). En ajouter une pour ce seul besoin contredit le Principe
VI (« ne pas réimplémenter/dépendre pour un besoin qu'une requête simple
couvre ») et les Principes de conception (« s'appuyer d'abord sur les
dépendances déjà présentes »). Le volume attendu (un club, quelques
signalements par semaine) ne justifie pas un magasin en mémoire partagé
(Redis) ni une dépendance dédiée : la table cible existe déjà, la requête est
un index sur `(ip_address, created_at)`.

**Alternatives considered**:
- Dépendance dédiée (`slowapi`) : rejetée — nouvelle dépendance pour un besoin
  qu'une requête SQL sur une table déjà nécessaire couvre entièrement.
- Compteur en mémoire du process : rejeté — plusieurs workers Render
  invalideraient la garde (chaque worker aurait son propre compteur), et l'état
  ne survit pas à un redéploiement. La table DB est déjà la source de vérité
  partagée par tous les workers.
- Pas de limite de débit du tout, honeypot seul : rejeté — l'issue demande
  explicitement de trancher l'anti-spam avant exposition publique ; un
  honeypot seul ne freine pas un bot qui ignore simplement le champ caché
  (comportement fréquent des scripts génériques qui remplissent tous les
  champs visibles du DOM).

## D2 — Honeypot : rejet silencieux sans persistance

**Decision**: le formulaire public embarque un champ caché supplémentaire
(invisible visuellement, hors du parcours clavier via `tabIndex={-1}` et
`aria-hidden`) que l'API attend vide. S'il est renseigné, `feedback_service`
répond par le même succès apparent (201, même forme de réponse) **sans
insérer** de ligne en base.

**Rationale**: renvoyer une erreur explicite apprendrait à un bot que son
remplissage a été détecté, l'incitant à s'adapter. Un faux succès n'a aucun
coût pour un émetteur humain (le champ est invisible et jamais rempli par un
navigateur normal) et n'ouvre aucune brèche : rien n'est stocké, rien ne
ressort côté admin.

**Alternatives considered**:
- Rejet explicite (422) : rejeté — signal exploitable par un bot pour ajuster
  son comportement.
- Marquer le signalement comme spam en base plutôt que ne pas l'insérer :
  rejeté — inutile pour cette v1 (pas de tableau de bord anti-spam demandé par
  l'issue) et complique le modèle (un statut de plus) pour zéro valeur métier.

## D3 — Lien de promotion GitHub : construction d'URL, aucun appel réseau

**Decision**: l'action « Promouvoir en issue GitHub » construit côté frontend
une URL `https://github.com/{repo}/issues/new?title=...&body=...`, `{repo}`
étant la même valeur littérale que `settings.github_repository`
(`Triathlon-Club-Nantais/data-triathlon`, `backend/app/core/config.py`) déjà
utilisée par `services/batch_runs.py` pour une fonctionnalité distincte
(déclenchement de workflows). La valeur est **dupliquée** côté frontend dans
une constante dédiée (`frontend/lib/github.ts`), sur le même patron que
`CLUB_NAME` (`frontend/lib/club.ts`) : « le front ne charge pas un endpoint
pour un texte statique ».

**Rationale**: l'issue écarte explicitement tout appel API GitHub ou GitHub
App pour cette itération, mais autorise un pré-remplissage « si c'est
simple ». Une URL de création d'issue avec paramètres de requête ne demande
aucun jeton, aucun appel réseau, aucune dépendance — seulement une
concaténation de chaînes côté client, ouverte dans un nouvel onglet.
Créer une route ou étendre un DTO existant pour relayer une chaîne statique
non secrète serait la surface d'API la plus chère possible pour la valeur la
plus stable du dépôt — précisément ce que `frontend/lib/club.ts` a déjà
tranché pour `CLUB_NAME`. Si le nom du dépôt change un jour, les deux
définitions changent ensemble, comme documenté pour `CLUB_NAME`.

**Alternatives considered**:
- Appel à l'API GitHub (`POST /repos/{repo}/issues`) pour créer l'issue
  directement : rejeté — explicitement hors périmètre v1 par l'issue.
- Lien statique vers la page d'issues du dépôt, sans pré-remplissage : rejeté
  — l'issue demande ce confort quand il est simple, et il l'est ici.

## D4 — Stockage de l'IP : champ interne, jamais exposé au détail admin

**Decision**: `user_feedback.ip_address` est stocké (nécessaire à D1) mais
n'apparaît dans aucun schéma Pydantic de lecture exposé à l'API
(`FeedbackRead` ne le porte pas). Le champ ne traverse jamais la frontière
HTTP vers le panel admin.

**Rationale**: l'assumption « vie privée » de la spec (aucune IP affichée en
clair dans la vue détail) doit rester vraie même si l'IP est nécessaire côté
serveur pour la limitation de débit. C'est la même distinction que la
constitution fait pour `ip_address` d'usage technique versus donnée
utilisateur affichée : le champ existe en base, il ne sort jamais dans une
réponse API destinée à l'affichage.

## D5 — Pouvoirs : lecture et gestion séparées, sur le patron `pending-providers`

**Decision**: deux pouvoirs, `FEEDBACK_READ` (lister, ouvrir le détail) et
`FEEDBACK_MANAGE` (changer le statut, enregistrer une URL GitHub de retour),
regroupés sous une nouvelle fonctionnalité `FEATURE_FEEDBACK = "Retours
utilisateurs"` dans `core/permissions.py`.

**Rationale**: réplique exactement `PENDING_PROVIDERS_READ` /
`PENDING_PROVIDERS_HANDLE` (`core/permissions.py`), le précédent le plus
proche fonctionnellement (une file de signalements publics à instruire). Une
lecture seule sans droit de traiter est un profil légitime (ex. un membre qui
consulte sans agir), donc les deux pouvoirs ne sont pas fusionnés.

**Alternatives considered**:
- Un seul pouvoir `FEEDBACK_MANAGE` couvrant lecture et écriture (patron
  `ALLOWED_EMAILS_MANAGE`) : rejeté — ce patron sert une ressource où lire sans
  pouvoir agir n'a pas de sens (gérer des adresses autorisées est un geste
  binaire) ; ici, consulter la liste des retours a une valeur propre.

**Note (post-`/speckit-analyze`, finding I2)**: les libellés affichés dans
`GET /admin/permissions` doivent dire « Consulter/Instruire les retours
utilisateurs », jamais « signalement(s) » — ce mot est déjà pris par
`PENDING_PROVIDERS_READ` (« Consulter les signalements », chronométreurs non
supportés) dans la même grille de composition des rôles. Le terme
« signalement » reste légitime dans la prose de spec.md/data-model.md, qui ne
s'affiche jamais à cet endroit.
