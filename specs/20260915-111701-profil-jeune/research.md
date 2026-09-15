# Research: Profil individuel jeune (#867)

## D1 — Nom des tables et modèles

**Décision** : `personal_profiles` (modèle `PersonalProfile`) et
`profile_log_entries` (modèle `ProfileLogEntry`).

**Rationale** : l'arbitrage de l'epic #863 demande un schéma générique, sans
préfixe « jeune » figé, pour ne pas bloquer une future extension aux adultes
— extension **non implémentée** ici. « Profil » est le terme neutre déjà
présent dans la demande de l'epic elle-même. `PersonalProfile` plutôt que
`Profile` seul : un `Profile` nu entrerait en collision de sens avec un futur
« profil de compte » (préférences d'affichage, etc.), pendant que « personal »
nomme précisément ce que porte la table — des informations personnelles d'un
individu suivi par le club, distinctes d'un compte applicatif (`User`).

**Alternatives envisagées** :
- `youth_profiles` / `youth_log_entries` — rejeté : préfixe figé, exactement ce
  que l'arbitrage de l'epic écarte.
- `members` / `member_profiles` — rejeté : `Athlete` porte déjà le sens
  « personne suivie par le club » côté résultats sportifs ; réutiliser
  « member » aurait suggéré un lien avec l'adhésion FFTRI, qui n'existe pas ici
  (un jeune encadré n'est pas nécessairement un `Athlete` scrapé).
- `individuals` — rejeté : trop générique, moins lisible en relecture de code
  que « profil », qui est le mot de l'epic.

**Ce que la table ne fait pas** : aucune colonne ne nomme « jeune » ni
n'entraîne de contrainte liée à l'âge. La restriction « jeunes uniquement pour
cette itération » vit **entièrement** dans la garde d'accès
(`jeunes:read`/`jeunes:write`), jamais dans le schéma — c'est ce qui permet une
future extension par un nouveau pouvoir (`adultes:*`, par exemple) sans
migration destructive.

## D2 — Forme du journal de bord

**Décision** : une table séparée `profile_log_entries`, une ligne par entrée
datée, clé étrangère `profile_id` vers `personal_profiles.id`. Colonnes :
`entry_date` (date de l'entrée, pas de l'écriture), `text` (`Text`, non vide),
`created_by_user_id` (qui a écrit l'entrée), `created_at` (horodatage
d'écriture, pour départager deux entrées de même date).

**Rationale** : patron directement repris de `VolunteerAction`
(`backend/app/models/volunteer_action.py`) — un journal est un historique,
jamais une valeur unique écrasée. L'issue #867 le demande explicitement
(« pas une note numérique »). Distinguer `entry_date` (métier — de quel jour
parle l'entrée) et `created_at` (technique — quand elle a été saisie) permet
une saisie a posteriori (un encadrant qui rattrape sa note le lendemain) sans
fausser l'ordre d'affichage voulu par l'utilisateur.

**Alternatives envisagées** :
- Une colonne `notes` en JSON sur `personal_profiles` (liste d'objets
  `{date, text}`) — rejeté : aucune requête possible (tri, comptage), aucune
  paternité par entrée sans dénormaliser dans le JSON, et le dépôt a déjà
  tranché ce débat en faveur d'une table séparée pour `VolunteerAction`.
- Une colonne `notes` texte libre unique, réécrite à chaque ajout (« ajouter
  au texte existant ») — rejeté explicitement par l'issue (« pas une note
  numérique » exclut aussi implicitement l'écrasement : un historique perdu
  n'est plus consultable après coup, contraire à FR-006 de la spec).

## D3 — Écran frontend minimal

**Décision** : deux pages sous `/admin/jeunes` (le libellé français de
l'entrée de navigation, patron `/admin/groupes`) — `page.tsx` (liste, cartes
mobile-first plutôt que le double-arbre grille/cartes de #461, puisque
l'usage principal décrit par #867 est le téléphone et qu'une table large n'a
pas de valeur ajoutée sur cet écran) et `[id]/page.tsx` (détail : informations
personnelles + historique du journal, formulaire d'ajout d'entrée si
`jeunes:write`).

**Rationale** : #461 (tableaux repliés en cartes) résout un problème que cet
écran n'a pas — un tableau dense utile en grand écran. Le profil d'un jeune
n'a que quelques champs et un historique textuel : une liste de cartes seule,
sans grille desktop, est le patron le plus simple qui satisfait pleinement le
besoin (Principe VI, YAGNI) et reste cohérent avec le mobile-first demandé.
La garde d'écriture suit le patron mesuré (#496) : `session.permissions`
lu côté client avant de rendre le formulaire de création/édition, jamais
comme substitut à la garde serveur.

**Alternatives envisagées** :
- Réutiliser le double-arbre grille/cartes de `LigneCarte.tsx` — rejeté :
  sur-ingénierie pour un écran dont l'usage desktop n'est pas demandé (#867
  ne mentionne que le téléphone), et zéro table dense à afficher.
- Une seule page combinant liste et détail (panneau latéral) — rejeté : casse
  le mobile-first (un panneau latéral suppose une largeur que l'écran cible
  n'a pas) et complique le partage d'URL d'un profil précis.

## D4 — Portée de `jeunes:write` sur cette feature

**Décision** : `jeunes:write` garde à la fois la création/modification du
profil **et** l'ajout d'une entrée de journal (hors flux d'appel de présence,
#869). C'est la description déjà posée dans le catalogue par #866
(`P.JEUNES_WRITE` : « Créer et modifier un profil jeune, (...) et ajouter une
entrée au journal de bord »).

**Conséquence sur le filet de test** : `tests/test_permissions_catalogue.py`
retire ses deux entrées `GARDE_A_VENIR` pour `jeunes:read` et `jeunes:write` —
les deux pouvoirs gardent désormais des ressources réelles posées par cette
feature. Rien n'est laissé pour #869, qui n'a besoin d'aucun nouveau pouvoir :
elle réutilisera `jeunes:write` sur la table `profile_log_entries` déjà en
place.
