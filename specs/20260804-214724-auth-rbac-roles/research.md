# Phase 0 — Recherche et décisions

**Feature** : RBAC — rôles composables · **Révisé** : 2026-08-05 (v3)

Tout ce qui suit a été vérifié sur le code de la branche, mesuré, ou sourcé. Les
numéros de ligne datent du relevé.

**Méthode de la v2** : cinq instructions parallèles — Casbin, modèle relationnel,
moteurs de politiques externes, puis deux adversaires chargés respectivement de
démolir le consensus obtenu et de prendre au mot l'exigence produit. Les
conclusions ci-dessous retiennent ce qui a survécu à cette confrontation ; ce qui
n'y a pas survécu est consigné, pas effacé.

**Ce que la v3 ajoute** : D11 et D12, issus de la revue humaine de la PR #193 —
la première confrontation de cette feature à un lecteur qui n'a pas le corpus du
dépôt en contexte. Elle a produit deux choses que le fan-out n'avait pas
produites : un objet manquant (les groupes) et une question mal posée (le patron
d'évolution des rôles semés). C'est la contre-épreuve de D0.

Puis **D13**, écrit après que `/speckit-analyze` a trouvé deux anomalies
critiques dans le contrat : il reprend à froid le choix de tenir la politique en
base, et **corrige le §D3**, dont la preuve empirique ne portait pas sur l'objet
qu'elle prétendait mesurer.

---

## D0 — La convergence des trois premières instructions était un artefact

Les trois premiers rapports recommandaient la même chose. Ce n'était pas trois
avis : c'était **un avis mesuré trois fois**, et la preuve est factuelle.

Les trois ont écrit que `Course` est unique par `(name, event_date, event_type)`.
Le modèle en porte **quatre** — `is_relay` depuis la migration `b2c3d4e5f6a7`.
L'erreur venait d'`AGENTS.md` et de la constitution, tous deux périmés. Trois
relevés indépendants du schéma ne reproduisent pas la même faute documentaire ;
trois lectures de la même documentation, si.

> **Corrigé sur `main` depuis** — commit `4570c12`, constitution amendée en
> **1.1.1** le 2026-08-05, Sync Impact Report compris. La tâche de correction que
> portait cette feature est devenue caduque au rebase, et l'issue d'amendement
> #198 sans objet. Le constat méthodologique, lui, reste : la faute a vécu assez
> longtemps pour être recopiée trois fois.

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
| Rôles eux-mêmes | **Base** | **Oui** | « Archiviste » naît sans PR. |
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

> ⚠️ **Ce dernier paragraphe est corrigé par [D13](#d13--la-politique-en-base--le-challenge-repris-à-froid-après-les-deux-anomalies)** :
> relues de près, #170 et #95 portent sur des **listes de données** (adresses
> autorisées, libellés de club), pas sur la composition d'un rôle. La mesure
> invoquée ne porte pas sur l'objet mesuré. La décision ne change pas — elle
> repose désormais sur l'exigence produit seule, ce qui est dit plutôt que
> déguisé en contrainte technique, comme pour `organisations` au Complexity
> Tracking.

### `is_superuser` — le booléen qui referme l'objection

L'objection sérieuse aux rôles en base était : *« une fonctionnalité livrée mardi
n'est administrable que si quelqu'un pense à cocher son pouvoir, sinon
l'administrateur perd silencieusement ce qu'on vient de livrer »*.

Un rôle porteur de `is_superuser` franchit **tout pouvoir, y compris ceux écrits
après lui**. Une livraison n'exige donc ni migration, ni recochage, ni même que
l'exploitant sache qu'elle a eu lieu. L'objection tombe pour un booléen.

### Aucune table `permissions` — mais les codes, eux, sont bien en base

C'est la décision qui rend cette option **moins chère** que les RBAC dynamiques
habituels : le catalogue vit dans l'application, la base ne stocke que le code.

*Cette phrase se lit de travers et l'a été (clarification du 2026-08-05) :*
« la base ne stocke que le code » veut dire qu'elle stocke **les codes portés par
les rôles**, en clair, dans `role_permissions` — et non la liste de référence des
codes possibles. Il n'y a pas de table de référence ; il y a bien des lignes.
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
confier « Archiviste » sans confier la suppression des courses.

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

---

## D11 — Les groupes d'appartenance : un objet manquant, dont le retard est gratuit

Relevé en revue humaine (#193), et **absent des cinq instructions de la v2** :
elles cherchaient toutes la meilleure façon de modéliser des *droits*, et un
groupe n'en est pas un.

Un rôle dit ce qu'on **peut faire**, un groupe à quoi on **appartient** — Codir,
techniciens, arbitres. Trois différences interdisent de replier l'un sur l'autre :
un groupe **existe même vide de droits** (un rôle sans pouvoir n'a aucun sens) ;
« lister les membres de X » n'est rendu proprement par aucune agrégation de rôles,
il faudrait convention-nommer un rôle et le détourner ; et l'appartenance et la
distribution de droits ont des **propriétaires métier différents**.

**Écarté vers #197, et c'est une asymétrie mesurable, pas un renvoi de
confort.** L'argument qui fait poser le modèle des rôles *maintenant* (D8) est
que le retard coûterait la réécriture de tous les tests de routes gardées.
Ici, l'inverse : tant qu'un groupe ne porte aucun droit, sa table n'intersecte
**aucune** décision d'accès — aucun test de garde ne la nomme, aucune route
protégée ne la lit. Le coût du retard est nul.

Il cesse de l'être à un moment précis, et c'est pourquoi #197 porte un jalon
plutôt qu'une priorité : **le jour où un groupe porte un droit** (patron GitHub
Teams — N rôles attachés à un groupe, l'union s'appliquant à ses membres). Ce
jour-là, les groupes entrent dans la décision d'accès et retombent exactement
dans le cas des rôles.

Le cadrage minimal est consigné dans #197 : deux tables, cinq ressources, trois
pouvoirs, et trois différences avec les rôles — pas d'`is_superuser` (un groupe
n'accorde rien), pas d'invariant du dernier administrateur (vider un groupe ne
verrouille personne), pas de non-amplification (il n'y a pas de pouvoir à
amplifier).

---

## D12 — Deux questions de la revue, résolues sans choisir dans les options offertes

### Le patron d'évolution des rôles semés

La revue offre trois voies pour l'enrichissement futur de `validator` :
organique, figé avec un `validator_v2` (patron GitLab), ou agrégation par
étiquette (patron Kubernetes `aggregate-to-*`). **Aucune n'est retenue, parce que
la question qui les précède n'avait pas été posée** : une migration a-t-elle le
droit de recomposer un rôle existant ?

Non — FR-041. Dès que FR-004 rend un rôle éditable à chaud, sa composition
devient une donnée d'exploitation. Une migration qui ajouterait `quality:comment`
à `validator` écraserait une décision d'exploitant sans laisser de trace, et
« l'exploitant l'avait justement retiré » est indistinguable de « il ne l'a pas
encore ajouté ».

Cette règle rend les trois voies sans objet : un pouvoir livré atteint
l'administration d'office (`is_superuser`), et les autres rôles par un appel
humain. Elle ne coûte **aucune ligne de code** — c'est une migration qu'on
n'écrit pas.

L'objection avancée contre la voie organique — « les définitions divergent entre
installations semées à des dates différentes » — est vraie et sans portée :
elle suppose un parc d'installations, il y en a une. Le patron GitLab existe
parce que GitLab doit à des millions d'installations une compatibilité que ce
projet ne doit à personne ; l'agrégation Kubernetes existe parce qu'un opérateur
tiers y injecte des rôles sans connaître le cluster. Importer l'un ou l'autre ici
serait le pis-aller inverse de l'habituel : de la complexité pour un problème
qu'on n'a pas.

### La portée de l'inventaire des pouvoirs

La revue oppose « voie AWS » (réservé aux gestionnaires) et « voie Kubernetes »
(`SelfSubjectRulesReview`, lisible par tout connecté), en notant que les codes
n'ont rien de secret. **C'est exact, et c'est pourquoi cet argument ne tranche
rien.**

Ce qui tranche : ouvrir l'inventaire à tout connecté créerait une classe de
ressource inexistante ailleurs dans cette feature — « authentifié, aucun pouvoir
exigé » — pour un consommateur qui n'existe pas. Le seul lecteur de l'inventaire
général est l'écran de composition des rôles, et il faut `roles:read` pour aller
au bout du geste. L'auto-inspection est servie par `GET /auth/me` (FR-020), qui
n'exige rien et qui rend désormais **aussi les rôles portés** — sans quoi
afficher « connecté en tant qu'administrateur » aurait exigé un appel que
`GET /admin/roles` refuse justement à qui n'a pas `roles:read`.

### La convention de nommage, figée avant que le catalogue grossisse

*(suite du D12)*

`<domaine>:<geste>` (FR-040), le geste nommant l'acte métier quand il en a un.
Elle est **dérivée des huit codes déjà posés**, non importée : `quality:override`
et `pending_providers:handle` nomment des gestes, `roles:read` / `:write` /
`:assign` retombent sur des verbes génériques faute de mieux. Réécrire
`quality:override` en `courses:update` par souci d'uniformité CRUD produirait un
pouvoir d'écriture générique sur les épreuves que personne ne détient et que
rien ne vérifie — le filet de FR-026 le refuserait le jour même.

---

## D13 — La politique en base : le challenge repris à froid, après les deux anomalies

Question posée le 2026-08-05, après que l'analyse a trouvé C1 et C2 : **pourquoi
la composition des rôles vit-elle en base plutôt qu'en code ?**

Elle mérite d'être reprise, parce que les deux anomalies découvertes
n'appartiennent à *aucune* autre partie de la feature. Elles sont la première
manifestation concrète du seul défaut structurel de ce choix : **la base et le
code peuvent diverger.**

### D'abord, ce qui est déjà en code — et que personne ne propose de déplacer

| | Où | Contesté ? |
| --- | --- | --- |
| Le point de contrôle (ressource → pouvoir exigé) | **Code** | Non — physiquement impossible autrement |
| L'inventaire des pouvoirs | **Code** | Non — c'est D3, et c'est ce qui évite une table `permissions` et son sync destructif |
| **Rôle → pouvoirs** | **Base** | **Oui, c'est l'objet du challenge** |
| **Les rôles eux-mêmes** | **Base** | **Oui** |
| Attribution utilisateur → rôle | **Base** | Non — personne ne propose de mettre des adresses en dur |

Le débat porte donc sur **deux lignes sur cinq**, pas sur « le RBAC en base ».

### Ce que « tout en code » supprimerait, chiffré

Les tables `roles` et `role_permissions`, six des neuf ressources
d'administration, la règle de non-amplification (FR-011), le pouvoir périmé
(FR-042), deux des trois chemins de verrouillage, et les refus de FR-006 et
FR-007. Soit **une dizaine des 63 tâches**, et **les deux anomalies critiques**
trouvées à l'analyse — qui n'existent que parce qu'un code peut disparaître du
catalogue en restant en base.

Ce serait un modèle plus petit, plus sûr, relu en revue de code, vérifié par le
typage : un `frozenset` mal orthographié est une erreur d'import, là qu'une
chaîne mal orthographiée en base est un silence.

### L'objection sérieuse, et elle n'avait pas été vue

Le §D3 justifie l'édition à chaud par un frottement **mesuré** : `autoDeploy:
false`, plus les issues **#170** et **#95**. Relues de près, ces deux issues ne
parlent **ni de composition de rôle ni de rôle du tout** :

- **#170** porte sur `AUTH_ALLOWED_EMAILS` — *« ajouter un contributeur exige un
  redéploiement Render »*. Ajouter un contributeur, c'est une **attribution** et
  une liste d'adresses. Les deux sont en base dans les deux modèles ;
- **#95** porte sur les libellés de club. Même nature : une **liste de données**
  coincée dans du code.

Autrement dit : **la preuve empirique invoquée mesure le frottement des listes,
pas celui de la composition des rôles.** Elle établit qu'il faut sortir les
listes du code — ce que font #170 et #95, et ce que fait déjà `user_roles` ici.
Elle n'établit rien sur la fréquence à laquelle un rôle est recomposé.

Ce point est retenu tel quel : le §D3 s'appuyait sur une mesure qui ne portait
pas sur l'objet mesuré.

### Pourquoi la décision ne change pas malgré cela

Trois raisons, dans cet ordre.

**1. C'est une exigence produit explicite, énoncée deux fois** (arbitrages du
2026-08-04 : « tout en base, éditable à chaud — rôles ET permissions créables
depuis une interface », puis « backend maintenant, écrans différés »). Le
Principe VI interdit l'abstraction spéculative, pas la satisfaction d'une
exigence exprimée. Une exigence produit ne se réfute pas par une mesure
technique — elle se chiffre, et le chiffre est ci-dessus.

**2. « Tout en code » est exactement le modèle v1**, annulé le 2026-08-04. Ses
motifs d'annulation — multi-club, plus de trois rôles, permissions par
fonctionnalité — sont **inchangés**. Y revenir ne serait pas une simplification,
ce serait un aller-retour, et le coût du retour a été chiffré : **+50 %** si la
migration suit immédiatement, **+120 %** après l'épique #81.

**3. Le vrai arbitrage est un taux.** Si un rôle est recomposé deux fois par an,
le code gagne ; tous les mois, la base gagne. Payer une dizaine de tâches pour ne
pas avoir à parier est une assurance, et la prime est nommée : c'est FR-042.

### Le taux, obtenu — et il ne mesurait pas ce qu'on croyait

Le propriétaire l'a donné le 2026-08-05 : **plus d'un pouvoir nouveau par mois**,
au rythme des features.

Ce chiffre ne départage **pas** base contre code, et c'est le piège de la
question. Un pouvoir naît de la ligne qui le vérifie (FR-002) : l'ajouter est un
événement de **code** dans les deux modèles. Le taux demandé portait sur la
**recomposition** d'un rôle — un geste d'exploitant —, celui obtenu porte sur
l'**allongement du catalogue** — un geste de développeur. Deux objets, deux
rythmes, aucun rapport de l'un à l'autre.

Il touche en revanche **FR-041**, et par un chemin qu'il fallait dérouler : à
douze pouvoirs par an, chacun devant revenir à un rôle non-administrateur exige
un geste manuel, sans rattrapage et sans alerte. Deux faits l'annulent :
l'administration reçoit tout d'office (`is_superuser`), et un pouvoir neuf ouvre
en général un **domaine** neuf, qui n'appartient à aucun rôle existant.

Arbitrage du 2026-08-05 : les features à venir ouvriront surtout des domaines
nouveaux. FR-041 est donc conservée telle quelle, avec un **déclencheur de
réouverture écrit dans la spec** — un domaine déjà couvert par un rôle
non-administrateur gagnant un troisième pouvoir. L'issue de rechange est alors
l'**absorption par domaine** (un rôle déclare absorber `quality:*`), dont
`is_superuser` est le cas particulier « absorbe tout » : une colonne, une clause,
et le motif d'agrégation que Mathieu proposait en D12 — écarté là comme
sur-outillage, il redeviendrait le bon outil à ce seuil précis.

### Ce que ce challenge change quand même

**Il nomme la dette au lieu de la laisser implicite.** FR-042 n'est plus « un cas
limite » : c'est *la* contrepartie permanente d'avoir mis la politique en base, et
la spec le dit maintenant en ces termes. C1 et C2 en étaient la première facture,
payée avant la première ligne de code parce qu'un lecteur humain a relu le
contrat.

**Un garde-fou envisagé et écarté** : journaler au démarrage les codes périmés
présents en base, sur le patron de `_warn_if_auth_unconfigured` (#114). Écarté —
`stale_permissions` les expose déjà à la lecture d'un rôle, et un avertissement de
démarrage pour un état qui se corrige en un `PATCH` serait de l'outillage pour un
problème qu'on n'a pas encore rencontré. À reprendre si la divergence se produit
réellement plus d'une fois.

**Un moyen terme nommé et rejeté** : composer les rôles `is_system` en code et
les rôles créés en base. Il contredit FR-006 (« un rôle livré doit rester
modifiable »), donne deux natures de rôle avec deux chemins d'édition, et ne
supprime pas FR-042 — les rôles créés divergeraient tout autant.
