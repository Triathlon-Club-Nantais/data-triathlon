# Phase 0 — Recherche et décisions

**Feature** : RBAC — rôles composables · **Révisé** : 2026-08-04 (v2)

Tout ce qui suit a été vérifié sur le code de la branche, mesuré, ou sourcé. Les
numéros de ligne datent du relevé.

**Méthode de la v2** : cinq instructions parallèles — Casbin, modèle relationnel,
moteurs de politiques externes, puis deux adversaires chargés respectivement de
démolir le consensus obtenu et de prendre au mot l'exigence produit. Les
conclusions ci-dessous retiennent ce qui a survécu à cette confrontation ; ce qui
n'y a pas survécu est consigné, pas effacé.

---

## D0 — La convergence des trois premières instructions était un artefact

Les trois premiers rapports recommandaient la même chose. Ce n'était pas trois
avis : c'était **un avis mesuré trois fois**, et la preuve est factuelle.

Les trois ont écrit que `Course` est unique par `(name, event_date, event_type)`.
Le modèle en porte **quatre** — `is_relay` depuis la migration `b2c3d4e5f6a7`.
L'erreur vient d'`AGENTS.md` et de la constitution (ligne 279), tous deux
périmés. Trois relevés indépendants du schéma ne reproduisent pas la même faute
documentaire ; trois lectures de la même documentation, si.

Conséquence méthodologique retenue : **ce qui a été confronté au code tient, ce
qui a été déduit du corpus ne tient pas.** Survivent le commun public global,
l'impossibilité d'un point de contrôle créé à l'exécution, le refus des moteurs
externes, la garde route par route. Ne survit pas ce qui répondait à une question
produit — notamment le refus de l'édition à chaud.

---

## D1 — Casbin : déconseillé, sur mesures

Instruit à fond, paquets réellement installés, décisions réellement chronométrées.

| Constat | Mesure |
| --- | --- |
| `uv add pycasbin casbin-sqlalchemy-adapter` installe **deux distributions revendiquant les 58 mêmes fichiers** | recouvrement 58/58, aucun avertissement |
| L'adapter SQLAlchemy **sync** est abandonné | dernier commit 2024-07-08, épingle `casbin>=0.8.1` (distribution figée depuis 2025-05-10) |
| Une virgule dans une valeur corrompt la policy | écriture silencieuse, `RuntimeError: invalid policy size` **au redémarrage suivant** |
| Le `deny` est O(n) — et c'est le chemin nominal du 403 | 79 µs à 23 lignes, **14 ms à 3 760 lignes** ; un `set` fait 0,7 µs |
| Sous les 40 threads AnyIO du projet | débit divisé par 7,9 → ~2 500 décisions/s |
| Recharger la policy par requête (pour satisfaire FR-016) | 11–44 ms contre **68 µs** de SQL indexé |
| Le watcher PostgreSQL (LISTEN/NOTIFY) | **inutilisable sur le pooler transaction de Supabase** (supavisor#85) |

Et le point qui tranche : **Casbin ne résout pas `POST /admin/pending-providers`**
— sa démonstration canonique (`keyMatch2` sur les chemins) *reproduirait* la
régression. Le filet reste requis à l'identique.

La seule forme défendable serait la policy en fichier versionné, l'appartenance
restant en SQL. Mais alors Casbin ne porte plus qu'une matrice statique, et
n'apporte plus que ~35 lignes de Python — au prix d'un couplage par chaîne non
vérifié par l'outillage : `require_permission("pending_providres")` refuserait
**tout le monde**, en silence.

## D2 — Moteurs de politiques externes : aucun ne convient

Sourcé et daté au 2026-08-04.

| Option | Verdict |
| --- | --- |
| **Oso (OSS)** | **Déprécié** — dépôt intitulé « Deprecated: See README », PyPI figé à 0.27.3 (2024-01-13). Seul Oso Cloud vit. |
| **Cerbos** | Le meilleur du lot, Apache-2.0, très actif. Mais **aucun mode embarqué Python** (le PDP WASM est JavaScript, et via le Hub payant) : un processus de plus. |
| **OpenFGA / SpiceDB** | Sur-dimensionnés — ReBAC pour un graphe de profondeur 2 fixe. OpenFGA impose en outre **son propre datastore**, donc la sortie des rôles hors de `users` : régression d'intégrité. |
| **Permit.io** | Seule option offrant une UI d'administration clés en main. Prix : la définition des droits chez un tiers SaaS, et des tests impossibles sans réseau ni Docker. |
| **Supabase RLS** | Hors sujet : le backend se connecte avec un rôle applicatif unique sans JWT Supabase, RLS filtre des lignes et ne sait pas rendre 403 sur un `POST`, et SQLite (dev + tests) n'a pas de RLS. |
| **Cedar / `cedarpy`** | Seul moteur déclaratif in-process. Mais liaison tierce mono-mainteneur sur un chemin de sécurité, et il ne dispense d'**aucune** table. |

Trois raisons communes, toutes ancrées dans ce dépôt : un PDP externe **casse le
Principe III** (Docker dans la suite unitaire, ou une doublure qui ne teste plus
la politique), **rouvre le levier de DoS** que #114 a fermé (appel réseau
bloquant, routes `def`, limiteur AnyIO à 40), et **coûte 7 $/mois minimum** sur
Render, les private services n'ayant aucun palier gratuit.

---

## D3 — Ce que l'exigence « éditable à chaud » veut vraiment dire

Le propriétaire a demandé : *« tout en base, éditable à chaud — rôles ET
permissions créables depuis une interface »*. Les trois premières instructions
ont répondu « non, en code ». **Ce refus n'était fondé qu'à moitié**, et
l'adversaire l'a établi.

La bonne découpe n'est pas « code contre base », c'est **point de contrôle contre
politique** :

| | Où | Éditable à chaud | Pourquoi |
| --- | --- | --- | --- |
| Ressource → pouvoir exigé | **Code** | **Non** | Un pouvoir naît de la ligne qui le vérifie. Aucun clic ne fait apparaître cette ligne. |
| Catalogue des pouvoirs | **Code**, servi par une route | Non | Mais il s'allonge seul à chaque livraison, et il est **affiché**. |
| Rôle → pouvoirs | **Base** | **Oui** | C'est la politique, pas le mécanisme. |
| Rôles eux-mêmes | **Base** | **Oui** | « Modérateur bénévolat » naît sans PR. |
| Attributions | **Base** | **Oui** | |

L'exigence est donc satisfaite **au maximum de ce qui est physiquement
possible**. Ce que le propriétaire n'obtiendra jamais — inventer un pouvoir — ne
représente aucune valeur perdue : une case qui ne commande rien.

**Le frottement est réel et documenté par le propriétaire lui-même**, ce que le
refus initial ignorait : `render.yaml:5` porte `autoDeploy: false # déploiement
uniquement via deploy hook (gate CI)`, et deux issues ouvertes disent le coût —
**#170** (« ajouter un contributeur exige un redéploiement Render […] le geste le
plus fréquent de l'administration et le plus coûteux ») et **#95** (mêmes mots
pour les libellés de club). Mettre la matrice de droits en dur reconduirait ce
frottement sur l'objet le plus susceptible de changer.

### `is_superuser` — le booléen qui referme l'objection

L'objection sérieuse aux rôles en base était : *« une fonctionnalité livrée mardi
n'est administrable que si quelqu'un pense à cocher son pouvoir, sinon
l'administrateur perd silencieusement ce qu'on vient de livrer »*.

Un rôle porteur de `is_superuser` franchit **tout pouvoir, y compris ceux écrits
après lui**. Une livraison n'exige donc ni migration, ni recochage, ni même que
l'exploitant sache qu'elle a eu lieu. L'objection tombe pour un booléen.

### Aucune table `permissions`

C'est la décision qui rend cette option **moins chère** que les RBAC dynamiques
habituels : le catalogue vit dans l'application, la base ne stocke que le code.
Comparaison chiffrée : une table coûterait ≈ 170 lignes, un chemin d'écriture au
démarrage, et le risque d'un **sync destructif** (un module non importé au boot
rend le catalogue partiel ; un sync qui supprime les absents efface des
attributions en production, sans bruit) — pour **zéro capacité supplémentaire**.

Le dépôt a déjà tranché ce débat deux fois : `Course.event_type` porte
`triathlon-m` en `String` nu avec la nomenclature en Python (`core/discipline.py`).
La règle du projet est constante — l'énumération vit en Python, la base stocke la
chaîne.

Le filet correspondant est un **test lisant l'AST** — patron déjà présent dans
`tests/test_core_http.py`, qui détecte tout `httpx` nu, alias compris, et se teste
lui-même. Il refuse la divergence dans les deux sens : un pouvoir déclaré que
personne ne vérifie, une garde citant un code inexistant.

---

## D4 — Le filet de non-régression change de nature, et il découvre une anomalie

**Constat de terrain** : le préfixe `/admin/` ne décrit pas l'audience —
`POST /admin/pending-providers` est le signalement anonyme du formulaire public
(`ScrapeForm.tsx:37`, `TcnScrapeForm.tsx:37`). La garde se pose route par route
(FR-018), ce que `tests/test_auth/test_public_routes_still_open.py:82` interdisait
déjà de contourner.

**Anomalie découverte en instruisant ce filet** :
`POST /api/v1/participations` et `DELETE /api/v1/participations/{id}` sont
**ouvertes à Internet** — `participations.py:105-113` fait `db.delete(row)` puis
`db.commit()` sans aucune garde. Et le filet actuel, écrit pour prouver
l'absence de régression sur le site public, **impose qu'elles le restent** : il
verrouille l'anomalie au lieu de la signaler. Arbitré le 2026-08-04 : elles
entrent dans le périmètre de cette feature.

**Forme retenue du filet** : l'inventaire reste **dérivé** du schéma OpenAPI ; une
table ne fait que **classer**. Trois assertions :

1. toute ressource `/api/v1/admin/*` non classée fait échouer la suite, en
   nommant la route — une nouvelle ressource d'administration ne peut pas naître
   sans que son auteur se prononce ;
2. toute ressource classée « gardée » rend 401 sans cookie et 403 avec une
   session sans pouvoir ;
3. toute ressource hors administration et hors `/auth/` ne rend ni 401 ni 403.

Ce que ce filet **ne prouve plus**, et qu'il faut écrire dans sa docstring : il
prouve qu'une ressource exige *un* pouvoir, jamais *qui* le porte — cette
seconde question est devenue une donnée. C'est le prix assumé de l'édition à
chaud, et il vaut mieux le nommer que de laisser croire le contraire.

---

## D5 — Le verdict de fiabilité : deux colonnes, une propriété hybride

`import_service.finalize()` (`import_service.py:311-320`) réécrit le verdict à
**chaque** import. Un avis humain sans place propre disparaîtrait au premier
re-scrape.

**Décision** : `is_reliable_computed` (l'import) et `reliability_override`
(l'humain), composées par une `hybrid_property` `is_reliable` =
`coalesce(override, computed)`, avec son `@expression` pour rester filtrable en
SQL — ce dont la sous-issue « Revalidation qualité » aura besoin.

Ce que cette forme **supprime** : la branche conditionnelle dans le chemin
d'import, le recalcul artisanal à la levée (qui devait relire
`quality_issues["duplicate_bib"]` pour reconstituer un argument perdu), et la
perte du verdict machine quand un humain tranche.

Le contrat public ne bouge pas : le DTO expose toujours `is_reliable`,
`from_attributes=True` lisant une propriété comme une colonne.

**Alternative rejetée** — colonne-drapeau `is_reliable_manual` + garde dans
`import_service` (v1 de ce plan) : elle marchait, mais écrasait le verdict
machine et exigeait deux astuces pour rester exacte. À défaire à la première
interface de revue.

---

## D6 — `require_permission`, et pourquoi maintenant

La garde nomme un **pouvoir**, jamais un rôle (FR-017), et compose
`current_user` — donc l'ordre 401-avant-403 est structurel : une requête sans
session n'atteint pas le corps de la garde.

Chaîne des couches, conforme au Principe II et calquée sur `deps.current_user` →
`services/auth/session` :

```
api/deps.require_permission(P.X)
  → services/auth/authorization.has_permission(db, user, permission)
    → repositories/user_role_repository.has_permission(db, user_id, code)
```

Une requête, trois tables jointes sur leurs clés indexées, `LIMIT 1`, avec
`OR roles.is_superuser IS TRUE`. Décidée à chaque requête (FR-016), aucun cache :
même raisonnement que l'invariant de session de #114, qui est une jointure.

**Pourquoi maintenant plutôt qu'après** — c'est le chiffre qui a tranché la
révision :

| Décision | Coût |
| --- | --- |
| Modèle complet maintenant | +905 lignes de backend, en remplacement de code non encore écrit |
| Plan v1 puis migration immédiate | ≈ 1 360 lignes, dont ~370 jetées (**+50 %**) |
| Plan v1 puis migration après l'épique #81 | ≈ 2 010 lignes, dont ~1 000 jetées (**+120 %**) |

Ce ne sont pas les `Depends(...)` qui coûtent, ce sont les ~50 lignes de test par
route affirmant « le validateur reçoit 403 ici », qu'il faudrait réécrire en
« qui ne porte pas `courses:delete` reçoit 403 ». Chaque sous-issue de #81 en
ajoute.

---

## D7 — Les deux garde-fous non négociables

**Le verrouillage se garde par l'état, pas par les chemins.** L'édition à chaud
multiplie les façons de se fermer dehors : retirer une attribution, supprimer un
rôle, décocher `is_superuser`, désactiver un compte — et chaque nouvelle façon
d'éditer les droits en ouvrira une cinquième. On vérifie donc **l'état
d'arrivée**, une fois, après `flush` et avant `commit` :
`assert_organisation_keeps_an_admin` → 409. Quatre sites d'appel, une
définition, et le cinquième chemin est couvert sans qu'on y pense.

**La non-amplification.** Nul n'accorde un pouvoir qu'il ne porte pas lui-même
(FR-011), et `is_superuser` n'est posable que par un superutilisateur (FR-010).
Sans cette règle, `roles:write` équivaut à `root` : quiconque édite les rôles se
fabrique en trois clics celui qui peut tout. Elle est sans effet pour un
superutilisateur — et c'est exactement ce qui rend la délégation possible :
confier « Modérateur bénévolat » sans confier la suppression des courses.

---

## D8 — Le multi-club est modélisé, pas exploité, et ce n'est pas un pis-aller

Les données du projet sont un **commun public** : `Course` est unique par
`(name, event_date, event_type, is_relay)` — deux clubs important la même épreuve
obtiennent la **même** ligne. Aucune donnée sportive ne peut porter une
organisation sans casser la déduplication. Vérifié : rien au catalogue n'en
apportera, **#105** (bénévolat) et **#106** (dashboards) sont fermées.

Il en découle que **toutes** les permissions de cette feature sont de portée
instance. `user_roles.organisation_id` existe, vaut l'organisation semée, et
aucune règle ne la consulte encore. Le jour où une ressource appartiendra à un
club, `has_permission` reçoit un paramètre et une clause — deux lignes. C'est la
**colonne** qui était chère à ajouter après coup, jamais le paramètre.

**Honnêteté sur l'argument technique** : « il faut créer `organisations`
maintenant, sinon un `batch_alter_table` SQLite » a été **mesuré et réfuté** —
`alembic/env.py:33` porte déjà `render_as_batch=True`, 5 des 8 révisions
l'emploient, et l'ajout après coup coûte 6 lignes et 8,1 ms sur 200 lignes, index
préservés. La table est créée sur **décision produit** (« modèle maintenant,
usage plus tard »), avec un gain technique secondaire : `organisation_id` non
nul, donc pas d'index partiel sur `NULL` à maintenir dans `user_roles`.

**`scope=club` n'est pas une organisation.** C'est un prédicat sur un libellé
**scrapé** (`core/club.py`, liste blanche, match à l'égalité), et deux
fournisseurs — runnerbreizh, chronoweb — ne publient aucun club : un membre y est
hors de `scope=club` tout en étant membre de l'organisation. Les fusionner ferait
d'un trou de données un trou d'autorisation. Leur rapprochement éventuel est
l'objet de #95, et il vit dans la couche repository, pas ici.

**Alternative écartée, mentionnée pour mémoire** : un club = une instance
(Render + Supabase), cloisonnement parfait par construction, coût marginal quasi
nul. Écartée par l'arbitrage « données partagées » — chaque instance rescraperait
tout, et les corrections de qualité ne circuleraient pas.

---

## D9 — La commande d'amorçage

`uv run python -m app.cli grant-role --email <adresse> --role <slug>`.
`create-admin`, proposé par l'issue #115, ment deux fois : la commande ne *crée*
pas d'utilisateur (il naît d'une connexion), et *l'*administrateur n'est pas
unique.

Codes de sortie conformes au Principe IV : `0` (attribué, ou déjà porté — FR-029),
`2` (adresse inconnue, adresse ambiguë, slug de rôle inconnu). L'ambiguïté n'est
pas théorique : `users.email` n'est **pas** unique par construction (#114,
documenté dans `models/user.py`).

Pas de `--json` : ce n'est pas un batch, il n'y a pas de bilan à piper.

---

## D10 — L'interface

Trois écrans seraient nécessaires pour piloter tout ceci (`/admin/roles`,
`/admin/roles/[id]`, `/admin/users`, ≈ 700 lignes). Ils sont **différés** à la
sous-issue d'interface de l'épique #81 : une fois le modèle en place, ce sont des
PR front pures, sans migration ni modification du backend. Dans l'intervalle,
`grant-role` donne exactement la capacité d'exploitation du plan v1.

**Un correctif d'affichage est toutefois inclus** : `PendingProvidersTable` ne lit
que `isLoading` et `data` ; sur un 403, `data` est `undefined` et le composant
affiche « Aucun fournisseur signalé ». Un utilisateur sans droit verrait un écran
**mensonger** au lieu d'un refus. `ApiError` porte déjà `status` — ~10 lignes.

**Trouvaille annexe** : `apiServer.listPendingProviders` (`lib/api/server.ts:90`)
n'a aucun appelant et passe par `serverFetch`, qui ne relaie pas les cookies.
Supprimée plutôt que laissée mûrir en 403.
