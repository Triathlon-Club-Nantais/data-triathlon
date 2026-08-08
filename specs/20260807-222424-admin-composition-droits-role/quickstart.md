# Quickstart — validation de bout en bout

Vérifie l'écran `/admin/droits` sur une base de développement. **Aucune
migration**, aucun changement de configuration : la feature ne touche que
`frontend/`.

## 0. Prérequis

```bash
# backend/ — base SQLite vierge, migrée, semée
cd backend
uv run python scripts/reset_db.py

# les trois rôles livrés doivent être là
sqlite3 triathlon.db "SELECT slug, is_system, is_superuser FROM roles;"
# admin|1|1 · validator|1|0 · moderator|1|0
```

```bash
# deux terminaux
cd backend  && uv run python scripts/dev_server.py   # publie son port
cd frontend && npm run dev                            # le lit
```

Un compte administrateur, si l'installation est neuve — l'ordre compte, un
utilisateur naît d'une connexion **autorisée** :

```bash
cd backend
uv run python -m app.cli allow-email --email <votre-adresse>
# … se connecter une fois via l'interface, puis :
uv run python -m app.cli grant-role --email <votre-adresse> --role admin
```

## 1. Tests automatisés

```bash
cd frontend
npm test            # Vitest + RTL — les trois fichiers de la feature doivent être verts
npm run lint
npm run build       # strict TS + RSC : la page doit compiler
```

```bash
cd backend
uv run pytest -m "not integration"   # doit rester vert : aucun fichier backend touché
```

## 2. Navigation (FR-021)

1. Se connecter avec le compte administrateur.
2. Dans la navigation, section « Gestion des utilisateurs » → **« Droits des
 rôles »** est cliquable et n'est plus annoncée comme à venir.
3. Elle mène à `/admin/droits`.

**Attendu** : l'entrée n'apparaît que pour qui porte `roles:write`. Se
déconnecter, se reconnecter avec un compte sans rôle : la section entière
disparaît (`AppNav` retire les sections que le filtrage vide).

## 3. Lecture (US1 — FR-001 à FR-005)

Sur `/admin/droits` :

- [x] Les trois rôles livrés sont listés, chacun avec son nom, sa description et

  son nombre de porteurs.
- [x] Déplier « Modérateur » : « Consulter les signalements » et « Instruire les

  signalements » sont cochés, **sous l'intitulé « Chronométreurs
  signalés »** — pas dans une liste plate, et jamais sous la seule forme
  `pending_providers:handle`.
- [x] Les sept fonctionnalités apparaissent dans l'ordre du serveur : « Rôles et

  accès », « Groupes d'appartenance », « Chronométreurs signalés »,
  « Qualité des données », « Épreuves », « Coureurs », « Résultats ».
  Comparer avec `curl` :
  
  `bash curl -s -b cookies.txt localhost:<port>/api/v1/admin/permissions | jq -r '.[].feature'` 

- [x] Déplier « Administrateur » : le panneau **annonce le statut** — franchit

  tout pouvoir, y compris ceux livrés après lui — et n'affiche **pas**
  dix-huit cases cochées.

## 4. Recomposition (US2 — FR-007, FR-008, FR-013)

- [x] Déplier « Validateur » (rôle **livré**) : le renommer en « Validateur

  qualité », enregistrer. Recharger : le nouveau nom tient. *Un rôle livré
  est modifiable — seule sa suppression est refusée (cf. `research.md` §D1).*
- [x] Lui cocher « Corriger une épreuve », enregistrer, recharger : le pouvoir

  est là.
- [x] Le décocher, enregistrer : il n'y est plus.

**Le renommage ne purge rien** (FR-007, FR-011) — à vérifier avec un code
périmé, ci-dessous.

## 5. Codes périmés (FR-004, FR-011, FR-016)

Fabriquer le cas : un code que l'inventaire ne connaît pas.

```bash
cd backend
sqlite3 triathlon.db "INSERT INTO role_permissions (role_id, permission_code)
                SELECT id, 'legacy:oldpower' FROM roles WHERE slug='validator';"
```

- [x] Recharger `/admin/droits` : `legacy:oldpower` apparaît dans un bloc

  **distinct** des cases de l'inventaire, annoncé comme périmé et sans effet.
- [x] **Renommer seulement** le rôle et enregistrer → recharger : le code périmé

  est **toujours là**. C'est l'invariant de `research.md` §D6 (`PATCH`
  n'envoie que ce qui a changé).
- [x] Modifier la composition et enregistrer : l'écran a prévenu que le code

  périmé disparaissait, et il a disparu.

```bash
sqlite3 triathlon.db "SELECT permission_code FROM role_permissions
                WHERE role_id=(SELECT id FROM roles WHERE slug='validator');"
```

## 6. Création et suppression (US3)

- [x] « Créer un rôle » : nom « Bénévole ». L'identifiant se propose tout seul

  (`benevole`) et reste corrigeable.
- [x] Cocher un pouvoir, valider : le rôle apparaît avec **0 porteur**.
- [x] Recréer un rôle avec le même identifiant : le refus du serveur s'affiche,

  la saisie est conservée.
- [x] Supprimer « Bénévole » (confirmation) : il disparaît.
- [x] Sur « Validateur » et « Administrateur » (livrés) : le bouton de

  suppression est **désactivé**, avec sa raison en texte.

Rôle porté, donc indélébile :

```bash
uv run python -m app.cli grant-role --email <votre-adresse> --role <slug-du-nouveau-role>
```

- [x] Recharger : la suppression de ce rôle est désactivée et annonce **le

  nombre de porteurs**.

## 7. Non-amplification (FR-014, SC-003)

Il faut un second compte, qui compose sans tout porter.

**Ne comptez pas basculer le rôle de votre propre compte** : `revoke_role` est
soumis à l'invariant du dernier administrateur (`authorization.py`), donc retirer
`admin` au seul compte qui le porte rend 409. Il faut un compte distinct.

1. Depuis le compte administrateur, créer un rôle « Gestionnaire de rôles »
   portant **uniquement** « Consulter les rôles » et « Composer les rôles ».
2. `allow-email` puis `grant-role` ce rôle à une seconde adresse, et s'y
   connecter (fenêtre privée).

Sans second compte auprès du fournisseur d'identité, `scripts/dev_login.py`
provisionne des comptes locaux et rend leur cookie de session — il traverse les
mêmes portes que `resolve_user` et refuse de s'exécuter hors SQLite. Le cookie se
pose sur **le front** (`localhost:3000`), pas sur le port du backend : le
navigateur appelle `/api/v1` en même origine et `next.config.ts` réécrit.

- [x] `/admin/droits` s'ouvre et liste les rôles.
- [ ] Sur n'importe quel rôle, les cases de « Chronométreurs signalés »,

  « Qualité des données », « Épreuves », « Coureurs », « Résultats » sont
  **désactivées dans leur état courant** — ni masquées, ni décochées — avec
  la raison affichée.
- [ ] Les deux cases de `roles:read` / `roles:write` sont, elles, basculables.
- [ ] **Ouvrir « Créer un rôle » et vérifier la même chose dans la modale** : les

  cases hors des deux pouvoirs portés y sont désactivées, exactement comme
  dans un panneau. C'est le chemin le plus contraint des deux —
  `create_role` soumet l'ensemble complet à la non-amplification, une
  modification n'en soumet que la différence.
- [ ] Aucune bascule du statut de superutilisateur n'est proposée à ce compte.
- [ ] Un code périmé reste retirable par ce compte (FR-016).

**Attendu global** : aucun geste offert par l'écran ne rend 403 ou 409 pour
cause de rôle livré, de rôle porté, ou de pouvoir non détenu.

## 7 bis. Consultation seule (FR-014b)

Troisième compte : un rôle portant **uniquement** « Consulter les rôles ».

- [ ] `/admin/droits` atteint par l'URL s'ouvre et liste les rôles — la

  navigation ne l'y mène pas, mais elle n'est pas une garde.
- [ ] Aucun bouton « Créer un rôle », « Enregistrer », « Supprimer » ni bascule

  de statut n'est rendu ; la phrase « Cet écran est en consultation » le dit.
- [ ] Toutes les cases sont désactivées, et les champs nom/description aussi.

## 7 ter. Écriture concurrente (FR-020c)

**Deux onglets suffisent, et le même compte** : le conflit porte sur le rôle
édité, pas sur une différence de droits. Chaque onglet monte son propre
`QueryClient` (`app/providers.tsx`), donc son propre cache.

**Le déclencheur n'est pas le retour de focus.** `providers.tsx` pose
`refetchOnWindowFocus: false` : revenir sur l'onglet A ne redemande rien. Il faut
une **mutation depuis A**, qui invalide `roles()` — et elle doit venir d'un geste
situé **hors** du panneau ouvert, sans quoi le brouillon meurt avec lui. « Créer
un rôle » est ce geste.

- [ ] Onglet A : ouvrir « Validateur », cocher « Corriger une épreuve », **ne pas**

  enregistrer.
- [ ] Onglet B : ouvrir « Validateur », cocher « Consulter les rôles », enregistrer.
- [ ] Onglet A : « Créer un rôle » → « Temporaire » → valider. L'invalidation

  ramène le rôle enrichi par B : un encadré annonce qu'il a été **modifié
  ailleurs**, et « Enregistrer » est désactivé.
- [ ] « Repartir de la version à jour » reprend le panneau sur l'état du serveur :

  la coche de B est là, celle de A a disparu — aucune n'a été écrasée en silence.
- [ ] Supprimer « Temporaire » pour laisser la base propre.

## 8. Refus de lecture (FR-017, FR-018)

- [x] Se connecter avec un compte portant **un seul** pouvoir hors du domaine

  des rôles (par exemple `quality:override`), puis atteindre `/admin/droits`
  directement par l'URL — la navigation ne l'y mène pas.
- [x] L'écran affiche « Accès refusé », **pas** une liste vide et **pas**

  « aucun rôle ».
- [x] Supprimer le cookie de session et recharger : le message parle de session

  expirée, distinct du précédent.

## 9. Dernier administrateur (bord)

Avec un seul rôle superutilisateur porté par une seule personne :

- [x] Tenter de retirer le statut de superutilisateur au rôle « Administrateur »

  → le serveur refuse (409), le message s'affiche **tel quel**, et le
  panneau retombe sur l'état du serveur (statut toujours posé).

## 10. Ce qui n'est pas vérifié ici

- L'attribution d'un rôle à une personne : c'est #239.
- Les groupes d'appartenance : c'est #241.
- Le comportement multi-organisations : l'installation n'a qu'un club, et les
rôles livrés sont globaux.

