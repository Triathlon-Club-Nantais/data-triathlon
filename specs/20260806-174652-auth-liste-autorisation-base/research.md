# Research — Liste d'autorisation en base

Phase 0 du plan. Huit décisions, chacune avec ce qui a été écarté et pourquoi.
Aucune `NEEDS CLARIFICATION` ne subsiste.

---

## R1 — Où la liste se lit, et pourquoi sans cache

**Décision.** `provisioning._is_allowed(db, email)` interroge
`allowed_email_repository.exists(db, email)`. Le service ne construit aucune
requête, le repository est la seule couche à toucher `Session` (Principe II).
`resolve_user` a déjà la `Session` sous la main : le changement est bien celui
d'une ligne annoncé par l'issue.

**Aucun cache, à aucun étage.** C'est la propriété qui *est* la feature :
`AUTH_ALLOWED_EMAILS` était lue une fois pour toutes parce que `get_settings` est
en `lru_cache`, et c'est précisément ce qui imposait le redéploiement. Ajouter un
cache TTL — même court — recréerait le défaut sous une forme plus difficile à
diagnostiquer : « c'est effectif tout de suite » deviendrait « au bout d'un
moment ». Le précédent est explicite dans `services/auth/authorization.py`, qui
relit les pouvoirs à chaque appel pour la même raison (FR-016 de #115).

**Le coût est mesuré et il est nul là où ça compte.** La lecture n'a lieu qu'au
**retour de parcours**, une requête déjà réseau-liée (deux allers-retours HTTP
vers le fournisseur). Le chemin authentifié chaud — `session.resolve`, appelé à
chaque requête du back-office — n'est **pas** touché : voir R4.

**Écarté.** *Un cache TTL de quelques secondes* : recrée le défaut de l'issue, au
bénéfice d'un `SELECT` sur une clé indexée d'une table de quelques dizaines de
lignes. *Charger la liste au démarrage dans une variable de module* : c'est
exactement `lru_cache`, déguisé.

---

## R2 — La reprise de production : une migration de données

**Le risque, nommé.** La production porte aujourd'hui des adresses réelles dans
`AUTH_ALLOWED_EMAILS`. Livrer la table vide, c'est mettre **tout le monde
dehors** au prochain déploiement — y compris les administrateurs, donc sans
recours par l'écran. C'est le scénario que SC-005 interdit.

**Décision.** La migration qui crée `allowed_emails` **insère dans la foulée** ce
que porte `AUTH_ALLOWED_EMAILS` dans l'environnement du processus, normalisé et
dédoublonné. Elle s'exécute au `alembic upgrade head` déjà présent dans le
`startCommand` de `render.yaml` (`uv run --no-sync alembic upgrade head && uvicorn …`),
donc **avant** que le serveur accepte la première requête. Variable absente ou
vide → aucune ligne insérée, ce qui est le cas nominal d'une base neuve.

**Pourquoi `os.environ` et pas `Settings`.** Le réglage disparaît de `Settings`
dans la même livraison (FR-012) ; la migration ne peut donc pas le lire par là.
La docstring de `core/config.py` — « plus aucun `os.getenv` éparpillé dans le
code » — porte sur le **code applicatif**, pas sur une migration, qui est un
script d'exploitation à usage unique et daté. L'exception est bornée à ce
fichier-là et ne se propage nulle part.

**Ordre d'exploitation, et pourquoi il est sûr.** `model_config` de `Settings`
porte `extra="ignore"` : une variable qui reste déclarée sur Render **après** la
livraison ne casse rien. La suppression de la variable dans le tableau de bord
est donc un geste de ménage, à faire *après* le déploiement, et
`docs/ci-cd.md` le dit dans cet ordre.

**Corrigé en revue de code** : cette section affirmait que l'entrée disparaîtrait
de `render.yaml` dans la même PR, au motif que `sync: false` signifie « valeur
saisie à la main » et que retirer la clé du blueprint ne supprime pas la valeur
posée. **Rien ne le vérifie**, et c'était le point de défaillance unique de la
mise en production : si l'hébergeur nettoie la variable en synchronisant le
blueprint, la migration lit une chaîne vide et ferme l'accès à **tout le monde**.
Aggravant, le rattrapage annoncé (`allow-email`) n'existe pas — les deux services
backend tournent en `plan: free`, qui n'ouvre aucun shell ; le seul recours est un
`INSERT` dans la console Supabase, désormais écrit dans `docs/ci-cd.md`.
L'entrée **reste donc déclarée** dans `render.yaml` le temps de cette livraison,
avec le commentaire qui dit pourquoi ; elle se retire dans une PR de suivi, une
fois la reprise constatée dans `/admin/acces`. Une ligne, et l'ordre 1-2-3 devient
impossible à inverser au lieu d'être seulement documenté.

**Écarté.** *Lancer `allow-email` à la main après le déploiement* : introduit
exactement la fenêtre que SC-005 interdit, et suppose qu'on y pense. *Lire
l'union environnement + base à l'exécution* : deux sources de vérité, interdit
par FR-012. *Une migration qui lit `Settings`* : impossible, le champ n'existe
plus — et le faire survivre juste pour la migration serait la couche de
compatibilité que le projet proscrit.

**Vérifiable.** `tests/test_migrations.py` sait déjà poser une variable
d'environnement (`monkeypatch.setenv`) et lancer `command.upgrade` sur une base
SQLite jetable : la reprise s'y teste sans machinerie nouvelle.

---

## R3 — Un seul pouvoir, dans une fonctionnalité qui existe déjà

**Décision.** Un membre ajouté à `P` :

```python
ALLOWED_EMAILS_MANAGE = Permission(
    "allowed_emails:manage",
    "Gérer les accès",
    "Consulter, ajouter et retirer les adresses autorisées à ouvrir une session.",
    FEATURE_ROLES,          # « Rôles et accès » — la fonctionnalité existe déjà
)
```

**Pourquoi un pouvoir et pas le rôle `admin`.** Le commentaire de l'issue demande
que seul un administrateur puisse le faire. `roles.is_superuser` **est** la
réponse : un rôle superutilisateur franchit tout pouvoir, présent et à venir
(#115). Nommer le rôle dans la garde ferait exactement ce que FR-017/FR-018 de
#115 interdisent, et rendrait la composition des rôles inopérante sur cette
ressource. Le résultat demandé est obtenu **sans migration, sans semis et sans
exception** : le rôle `admin` franchit le pouvoir le jour de la livraison.

**Pourquoi un seul code et pas la paire `read` / `write`.** Le catalogue emploie
des paires ailleurs (`roles:read` / `roles:write`), mais elles ont un lecteur
distinct : on consulte les rôles pour comprendre qui peut quoi, sans les éditer.
Ici, la liste n'a **aucun autre consommateur** que l'écran qui la modifie — un
porteur du seul `read` regarderait un écran sur lequel tous les gestes échouent.
Deux codes coûteraient un membre de `P`, une case de plus dans la composition des
rôles et une garde de plus, pour un rôle que personne ne composerait : c'est de
la flexibilité morte (Principe VI).

La décision est **réversible sans migration** — scinder en `allowed_emails:read`
et `:write` reste un ajout de membre à `P` (FR-014 de #115), pas un changement de
schéma. C'est ce qui autorise à commencer simple.

**Pourquoi `FEATURE_ROLES` et pas une fonctionnalité nouvelle.** Le libellé
existant est « Rôles **et accès** ». Créer un cinquième groupe pour un pouvoir
unique allongerait l'écran de composition sans rien clarifier.

**Le prix, nommé.** Un porteur de ce pouvoir peut **fermer l'accès de n'importe
quel compte** — le retrait désactivant ses titulaires (R4) — sans traverser la
non-amplification de #115, qui ne garde que l'octroi de pouvoirs. Le plafond est
l'invariant du dernier administrateur (R5), qui borne les dégâts sans les
interdire. Scinder le pouvoir en `read`/`write` n'y changerait rien : c'est
l'effet du retrait qui porte le privilège, pas le nombre de codes. Le noter ici
évite qu'on le redécouvre en le prenant pour un oubli.

**Écarté.** *Une garde nommant le rôle `admin`* : viole FR-017 de #115 et fige la
composition. *Un pouvoir par geste* (`:read`, `:add`, `:remove`) : trois codes
pour un écran à trois boutons dont personne ne dissociera jamais les droits.

---

## R4 — Le retrait désactive, l'ajout réactive

**Décision.** Retirer une adresse supprime sa ligne **et** passe
`is_active = False` sur les utilisateurs qui la portent
(`user_repository.find_by_email`, qui rend une **liste** — `users.email` n'est pas
unique). Ajouter une adresse insère la ligne **et** repasse ces mêmes
utilisateurs à `is_active = True`.

**Pourquoi la désactivation.** Le retrait doit être effectif au geste (FR-016).
Sans lui, la liste n'est consultée qu'à la connexion : une session ouverte
survivrait jusqu'à sept jours, et l'écran afficherait « retiré » pour quelqu'un
qui continue de naviguer. `is_active` fait tomber les sessions **immédiatement**
parce que l'invariant de `session.resolve` est une jointure, jamais un cache
(#114) — aucune ligne de `user_sessions` n'est à parcourir, et
`session.resolve` n'est pas modifié.

**Pourquoi la réactivation n'est pas optionnelle.** Sans elle, réinscrire une
adresse ne rouvrirait rien : `provisioning.resolve_user` refuse en
`account_not_allowed` un utilisateur désactivé, avant même de regarder la liste.
L'exploitant verrait l'adresse dans le tableau et la personne resterait dehors,
sans message qui l'explique. La symétrie est ce qui rend le geste réversible
(FR-017).

**Le couplage assumé, et son échéance.** `is_active` acquiert ici un second
producteur. Aujourd'hui il n'en a **aucun** — rien dans l'application ne
désactive un compte, la colonne n'est mise qu'à `True` à la création — donc le
conflit est nul à la livraison. Il naîtra avec #169 (révocation d'urgence) : à ce
moment-là, réinscrire une adresse pourrait défaire une révocation délibérée.
C'est à #169 de trancher, et elle devra le faire de toute façon puisque son objet
est précisément de distinguer « fermé parce que retiré » de « fermé parce que
révoqué ». Le noter ici est ce qui évite qu'on le redécouvre en incident.

**Écarté — et c'est l'alternative sérieuse.** *Joindre `allowed_emails` dans
`session.resolve`*, ce qui donnerait le même effet immédiat sans toucher à
`is_active`, rendrait la réactivation inutile et supprimerait le couplage avec
#169. Rejeté pour deux raisons : (1) il modifie la requête la plus sensible de
l'application, exécutée à **chaque** requête authentifiée, pour un besoin
d'exploitation ; (2) il double les conditions de l'invariant à trois branches
documenté par #114, et l'invariant du dernier administrateur (R5) ne le verrait
pas — `count_active_superusers` compte des comptes **actifs**, pas des comptes
autorisés, et il faudrait donc écrire une seconde règle au lieu de réutiliser la
première. Le choix retenu paie un couplage documenté et daté ; l'alternative
payait une complexité permanente sur le chemin chaud.

---

## R5 — Le verrouillage total se garde par réutilisation

**Le trou, nommé.** Puisque le retrait désactive (R4), retirer l'adresse du
dernier administrateur actif ferme le back-office **pour tout le monde**, sans
recours autre que la CLI sur le serveur.

**Décision.** Le retrait s'exécute dans
`authorization.administrateurs_preserves(db)`, le gestionnaire de contexte de
#115, sans argument d'organisation — donc sur **toutes** les organisations.
`count_active_superusers` filtre déjà `User.is_active.is_(True)` : la
désactivation fait mécaniquement chuter le compte, et l'invariant lève
`LastAdministratorError` (409) avant que la transaction ne soit validée. **Zéro
règle nouvelle.**

**Pourquoi pas « on ne retire pas sa propre adresse ».** C'est la règle qui vient
à l'esprit, et elle est à la fois trop stricte et trop laxiste : trop stricte
parce qu'un administrateur qui quitte le club, alors qu'un autre reste, a le
droit de se retirer ; trop laxiste parce qu'avec deux administrateurs, retirer
**l'autre** verrouille tout autant si le premier n'est plus actif. La contrainte
porte sur la **perte** du dernier administrateur, pas sur l'identité de qui
demande — c'est exactement la nuance que #115 a déjà tranchée et qu'il serait
absurde de retrancher ailleurs.

**409 et non 403**, pour la même raison qu'en #115 : l'appelant *est*
administrateur, sa requête est bien formée, c'est le **résultat** qui est
interdit.

---

## R6 — Le garde de configuration perd la liste

Décision détaillée dans `plan.md` §Complexity Tracking (seul écart au Principe
IV). En résumé : `Settings.auth_is_configured` ne garde plus que la clé de
signature et l'origine de retour ; `GET /auth/methods` n'interroge aucune table ;
`main._warn_if_auth_unconfigured` cesse de citer le réglage. Le fail-closed
reste entier là où il décide — `provisioning` refuse en `account_not_allowed`,
liste vide comprise, et le test qui le vérifie existe déjà.

**Conséquence à assumer et à documenter** : sur une installation neuve, la page
de connexion **affiche** son bouton et la connexion échoue au retour, avec le
message « compte non autorisé » déjà traduit. C'est moins bavard qu'un écran
« aucun moyen de connexion » — mais c'est aussi la seule situation où le
diagnostic est trivial, puisque le refus est journalisé avec l'adresse soumise.

---

## R7 — L'idempotence se joue sur la contrainte, pas sur une lecture

**Décision.** `UNIQUE` sur `allowed_emails.email`. L'insertion est tentée sous
`SAVEPOINT` (`db.begin_nested()`), et une `IntegrityError` est rattrapée en
relisant la ligne existante — le patron **exact** de
`user_role_repository.grant`, qui rend `(ligne, créée)`.

**Pourquoi pas « lire puis insérer ».** Deux exploitants simultanés franchissent
une lecture préalable ; ils ne franchissent pas la contrainte. Le `SAVEPOINT` est
ce qui permet de rattraper la violation sans perdre la transaction en cours — et
c'est déjà le raisonnement écrit dans le dépôt, à copier plutôt qu'à redécouvrir.

**Le retrait est idempotent par nature** : ligne absente → `204`, aucun effet,
aucune erreur (patron de `user_role_repository.revoke`).

---

## R8 — La validation d'adresse, sans dépendance nouvelle

**Décision.** `EmailStr` de Pydantic v2 sur le DTO d'entrée. `email-validator`
est déjà installé — `fastapi[standard]` le tire (`backend/uv.lock`), donc
`uv sync --frozen --no-dev` l'a en production. Rien à ajouter à
`pyproject.toml`.

**Normalisation.** L'adresse est **rangée en minuscules, espaces de bordure
retirés**, à l'écriture comme à la lecture. La normaliser à la source est ce qui
rend la contrainte `UNIQUE` suffisante et la comparaison de connexion triviale —
sans quoi il faudrait un index fonctionnel `lower(email)` en PostgreSQL et une
comparaison insensible à la casse à chaque lecture. Le côté connexion compare
`identity.email.strip().lower()`, comme aujourd'hui.

`user_repository.find_by_email` compare déjà `func.lower(User.email)` : la
désactivation de R4 retrouve donc les comptes quelle que soit la casse rendue par
le fournisseur.

**Écarté.** *Une expression régulière maison* : réimplémente une bibliothèque
déjà installée. *Aucune validation* : FR-010 l'exige, et une adresse mal saisie
dans une liste d'autorisation est silencieuse — elle n'échoue jamais, elle
n'autorise simplement personne.
