# Quickstart — valider le socle d'authentification en local

Phase 1. Ce guide prouve la feature **de bout en bout**, dans un navigateur. Il complète les tests
automatisés, qui ne peuvent ni créer une application OAuth ni donner un consentement humain.

---

## Avertissement : worktree principal seulement

L'authentification n'est utilisable **que depuis le dépôt principal**, pas depuis un worktree.

Deux raisons, cumulatives. `frontend/scripts/dev.mjs` lance `next dev` **sans `--port`** : le second
worktree atterrit sur `:3001` sans que personne le sache. Et une application OAuth GitHub n'accepte
**qu'une seule** URL de retour, port compris. Un retour figé sur `:3000` renverrait donc le second
worktree vers l'interface — et la base — du premier, **sans erreur visible**.

Corollaire pour `backend/.env`, que `.worktreeinclude` recopie dans chaque worktree : **n'y figez
pas** `AUTH_REDIRECT_BASE_URL` ni les identifiants OAuth.

---

## 1. Créer une application OAuth GitHub

Sur <https://github.com/settings/developers> → **New OAuth App**.

| Champ | Valeur |
| --- | --- |
| Application name | `data-triathlon (local)` |
| Homepage URL | `http://127.0.0.1:3000` |
| Authorization callback URL | `http://127.0.0.1:3000/api/v1/auth/github/callback` |

**Le retour vise l'interface, jamais le backend.** L'interface proxifie `/api/*` ; le navigateur ne
voit donc qu'une seule origine, et c'est à elle que les cookies sont attribués. Un retour pointant
sur le port du backend court-circuiterait ce proxy : le cookie d'état, posé sur l'origine de
l'interface, ne serait jamais renvoyé, et **tout** retour de parcours échouerait en
`state_mismatch`. C'est la leçon la plus coûteuse de la PR #159.

Notez le **Client ID**, puis générez un **Client secret**.

---

## 2. Renseigner `backend/.env`

> **Le nom du fichier est `backend/.env`, exactement.** `pydantic-settings` ne lit
> que celui-là (`core/config.py`, `env_file=".env"`). Un fichier nommé
> `.env.local` — la convention du **frontend** — laisse le backend démarrer
> normalement, avec toutes les valeurs vides : `/auth/methods` rend alors `[]` et
> l'écran de connexion annonce « aucun moyen de connexion » sans autre indice.
> Le démarrage journalise désormais un avertissement qui nomme les réglages
> absents. Et `get_settings` étant en `lru_cache`, **redémarrez le backend** après
> toute modification du fichier.

```bash
AUTH_SESSION_SECRET_KEY=<au moins 32 caractères — voir ci-dessous>
AUTH_GITHUB_CLIENT_ID=<Client ID>
AUTH_GITHUB_CLIENT_SECRET=<Client secret>
AUTH_ALLOWED_EMAILS=<votre adresse GitHub vérifiée>
AUTH_REDIRECT_BASE_URL=http://127.0.0.1:3000
AUTH_COOKIE_SECURE=false
```

Génération de la clé :

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Trois pièges, chacun conçu pour échouer bruyamment :

- une clé de moins de 32 caractères **refuse le démarrage** ;
- `AUTH_ALLOWED_EMAILS` **vide** interdit toute connexion et fait rendre `[]` à `/auth/methods` —
  c'est voulu, une liste vide n'a jamais valu « tout le monde » ;
- `AUTH_COOKIE_SECURE=false` est **obligatoire en local** (le site est en clair), et retire le
  préfixe `__Host-` du nom des cookies. En production, `true`.

L'adresse doit être **vérifiée** chez GitHub, sinon la connexion est refusée en `email_unverified`
avant même l'examen de la liste.

---

## 3. Appliquer la migration et démarrer

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python scripts/dev_server.py
```

Dans un second terminal :

```bash
cd frontend
npm run dev
```

Vérifiez que l'interface écoute bien sur **3000** — sinon, relisez l'avertissement en tête.

---

## 4. Dérouler le parcours

| # | Action | Attendu |
| --- | --- | --- |
| 1 | Ouvrir `http://127.0.0.1:3000` | Le site fonctionne, un bouton **Se connecter** apparaît dans la barre. |
| 2 | Ouvrir `/admin` **sans session** | Redirection vers `/login`. |
| 3 | Cliquer sur **Se connecter** | La page `/login` affiche **un bouton GitHub**, rendu depuis `/auth/methods`. |
| 4 | Cliquer sur **GitHub** | Redirection vers GitHub, écran de consentement. |
| 5 | Autoriser | Retour sur `/admin`, **connecté**. Le menu utilisateur affiche votre adresse. |
| 6 | Rafraîchir la page | Toujours connecté. |
| 7 | Fermer l'onglet, rouvrir le site | Toujours connecté. |
| 8 | Ouvrir `/admin` | La page s'affiche. |
| 9 | **Se déconnecter** | Retour à l'état anonyme, `/admin` redirige de nouveau vers `/login`. |

---

## 5. Vérifier ce qui ne se voit pas

**Les cookies** (outils de développement → Application → Cookies) :

- `tcn_session` est présent, `HttpOnly` **coché**, `SameSite=Lax`. Il doit être **illisible** depuis
  la console : `document.cookie` ne doit pas le contenir.
- `tcn_auth_state` **a disparu** après le retour de parcours. S'il subsiste, l'usage unique est
  cassé.

**La base** — le jeton du cookie ne doit **exister nulle part** :

```bash
cd backend
uv run python -c "
from app.core.database import SessionLocal
from app.models.user_session import UserSession
with SessionLocal() as db:
    for s in db.query(UserSession).all():
        print(s.user_id, s.token_hash, s.expires_at)
"
```

Comparez : `token_hash` fait 64 caractères hexadécimaux et **ne ressemble pas** à la valeur du
cookie. Chercher la valeur du cookie dans la table ne doit rien rendre.

**Le site public est intact** — sans aucun cookie :

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/api/v1/courses
```

Attendu : `200`, comme avant la feature.

---

## 6. Dérouler les refus

Chacun doit ramener sur `/login` avec un message **français**, et **jamais** afficher une page de
données techniques.

| Cas | Comment le provoquer | Code attendu |
| --- | --- | --- |
| Adresse non autorisée | Retirer votre adresse d'`AUTH_ALLOWED_EMAILS`, redémarrer, se reconnecter | `account_not_allowed` |
| Preuve d'origine absente | Supprimer le cookie `tcn_auth_state` avant de revenir de GitHub | `state_mismatch` |
| Preuve rejouée | Recharger l'URL de retour une seconde fois | `state_mismatch` |
| Refus chez GitHub | Cliquer sur **Cancel** sur l'écran de consentement | `provider_error` |
| Authentification non configurée | Vider `AUTH_GITHUB_CLIENT_ID`, redémarrer | `/auth/methods` rend `[]`, la page de connexion l'annonce, **le site public fonctionne** |

Après chaque refus : **aucun** nouvel utilisateur en base.

```bash
cd backend
uv run python -c "
from app.core.database import SessionLocal
from app.models.user import User
with SessionLocal() as db:
    print(db.query(User).count(), 'utilisateur(s)')
"
```

---

## 7. Vérifier la révocation

Session ouverte, désactivez le compte :

```bash
cd backend
uv run python -c "
from app.core.database import SessionLocal
from app.models.user import User
with SessionLocal() as db:
    u = db.query(User).first(); u.is_active = False; db.commit()
    print('désactivé :', u.email)
"
```

Rafraîchissez la page : vous devez être **immédiatement** déconnecté, sans avoir touché à la table
des sessions. C'est l'invariant à trois conditions de FR-013 qui le garantit.

---

## 8. Ce que ce guide ne couvre pas

Le reste est couvert par la suite automatisée, qui n'a besoin d'aucun réseau :

```bash
cd backend && uv run pytest -m "not integration"
cd frontend && npm test
```

Y figurent notamment les cas qu'un navigateur ne permet pas de provoquer commodément : preuve
d'origine émise pour un autre moyen de connexion, adresse non certifiée, absence d'appel réseau sur
les chemins d'échec local, inaccessibilité de la doublure de test dans le registre chargé à froid,
et non-régression de **chaque** route publique existante.
