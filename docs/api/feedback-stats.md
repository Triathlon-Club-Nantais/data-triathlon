# Retours utilisateurs et statistiques de participation

Renvoyé depuis `backend/app/api/AGENTS.md`.

## Retours utilisateurs (#267)

Une ressource, **deux modules, et c'est le chemin qui trie** : la soumission
vient du bouton flottant du site, chez un visiteur anonyme — elle est publique,
donc elle vit sous `/feedback` (`feedback.py`). La consulter et l'instruire
exigent chacun leur pouvoir, donc elles vivent sous `/admin/feedback`
(`admin_feedback.py`), où **rien** n'est public.

| Ressource | Module | Pouvoir |
| --- | --- | --- |
| `POST /feedback` | `feedback.py` | aucun — publique |
| `GET /admin/feedback`, `GET /admin/feedback/{id}` | `admin_feedback.py` | `feedback:read` |
| `GET /admin/feedback/counts` | `admin_feedback.py` | `feedback:read` |
| `PATCH /admin/feedback/{id}` (`status`, `github_url`) | `admin_feedback.py` | `feedback:manage` |

- **La liste est une file de traitement, pas un journal** (#500) :
  `GET /admin/feedback` accepte un `status` facultatif — omis, elle rend toute
  la table, sa forme d'origine, donc la v1 publiée ne bouge pas ; fourni hors
  des quatre valeurs de `FEEDBACK_STATUSES`, c'est un 422, le type du paramètre
  étant **dérivé** de cette nomenclature (`Literal[*FEEDBACK_STATUSES]`) et non
  réécrit. Le filtre s'appuie sur `ix_user_feedback_status_created_at`, l'index
  que le modèle porte depuis #267.
- **`/counts` est une route à part, et déclarée avant `/{feedback_id}`.** À part
  parce qu'envelopper la liste dans une page pour y loger des totaux serait un
  changement de contrat de v1 (Principe IV, patron de `GET /courses/count`) ;
  **avant** parce que FastAPI résout les chemins dans l'ordre de déclaration —
  l'inverse ferait lire « counts » comme un identifiant entier, soit 422 sur une
  route qui existe. Elle rend **toujours** les quatre statuts, à zéro le cas
  échéant : c'est ce qui permet au front d'afficher ses quatre filtres sur une
  base vide. Le repository, lui, ne rend que les statuts présents — compléter
  les manquants est une décision d'affichage, elle appartient au routeur.
- **Pourquoi pas tout sous `/admin`** (revue de #315) : un verbe public y aurait
  côtoyé trois verbes gardés, et se serait lu comme une garde oubliée. Le cas
  existe encore une fois dans l'API — `POST /admin/pending-providers`, publique
  et sous `/admin` — mais celle-là est **publiée** sous `/api/v1`, donc figée
  par le Principe IV. Elle reste l'exception nommée dans
  `test_public_routes_still_open.py`, elle ne devient pas le patron.

- **`ip_address` ne sort jamais** d'un schéma de lecture (`FeedbackRead`) : elle
  ne sert qu'à `count_recent_by_ip`, la limitation de débit par IP (#267,
  research.md §D1). D'où vient cette IP est une **décision**, prise dans
  `app/main.py` (#393) : uvicorn lit `X-Forwarded-For` par défaut et en retient
  la dernière entrée non fiable, or Render **préfixe** l'en-tête de l'IP réelle
  et laisse derrière elle ce que l'appelant a écrit — la valeur retenue était
  donc celle de l'appelant, et le plafond se contournait en faisant varier
  l'en-tête (mesuré sur preview : 7 envois, 7 × 201 pour une limite de 5). Un
  `ProxyHeadersMiddleware` monté avec `trusted_hosts="*"` retient la
  **première** entrée, la seule que la plateforme pose. Le réglage vit dans
  l'application et non dans le `startCommand` : `render.yaml` n'est appliqué
  par personne (cf. son propre en-tête).
- **`email` est résolu par jointure** (`UserFeedback.user`), jamais par une
  seconde requête : `feedback_repository.get` et `list_sorted` chargent la
  relation en `joinedload`, même patron que `allowed_email_repository`.
- **Honeypot silencieux** (research.md §D2) : un champ caché rempli répond le
  même succès apparent qu'une insertion réelle, sans qu'aucune ligne n'existe —
  `id=0` n'est jamais une clé réelle.

## Statistiques détaillées d'une participation (#272)

`GET /participations/{id}` porte un champ `stats` (`ParticipationStatsOut | None`)
qui compare l'athlète au **classement complet** de sa course : évolution du rang
par étape, comparaison aux positions de référence (1er, 10e, 25e, 50e, 100e),
simulation de gains par amélioration. Calculé à la lecture par
`services/participation_stats_service.py`, jamais persisté.

Quatre points à ne pas défaire :

- **Le calcul est réservé à la lecture d'une seule participation.** Le champ
  appartient à `ParticipationOut`, donc il **apparaît** aussi sur
  `GET /courses/{id}`, `GET /athletes/{id}` et `GET /participations` — toujours
  à `null`, sans qu'aucun classement n'y soit parcouru. Le peupler sur une route
  de liste ferait un parcours de classement complet **par ligne**.
- **L'éligibilité vit dans `core/splits_reliability.py`, et nulle part
  ailleurs.** C'est une liste d'**exclusion** (`t2area`, `breizhchrono`, plus la
  saisie `manuel`) : un fournisseur nouvellement enregistré est éligible par
  défaut. Une liste blanche se périmerait en silence à chaque scraper ajouté.
  Sa mise à jour accompagne l'évolution du scraper concerné, dans la même PR.
- **`stats: null` est le seul signal d'indisponibilité.** Course non éligible et
  participation de relais rendent le même `null` ; le front en tire son état
  « statistiques indisponibles ». Pas de booléen séparé à tenir en cohérence.
- **Les temps se lisent en `strict=True`.** `to_seconds` permissif ramène
  l'illisible à `0`, et un zéro se lit ici comme un temps parfait. Un segment
  absent doit rester absent — c'est ce qui distingue « non publié » de
  « instantané ».

Spec, plan et tâches : `specs/20260813-163525-resultats-detail-participation/`.
