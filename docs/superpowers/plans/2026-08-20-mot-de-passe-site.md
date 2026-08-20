# Mot de passe d'accès au site (#509) — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fermer l'accès public au site entier (front + API) derrière un mot de passe partagé aux adhérents, distinct du mot de passe bénévoles (#271).

**Architecture:** Reprend le patron HMAC+scrypt de #271, factorisé dans un module neutre `services/shared_password.py`. Nouvelle table `site_access_config` (une ligne), nouvelle garde `require_site_access` posée à l'inclusion de chaque router (sauf `health`, `site_access`, `benevoles`), nouveau cookie `tcn_site_session` avec expiration serveur (TTL, pas de renouvellement glissant). Côté frontend, un groupe de routes `app/(protege)/` porte la garde par layout (jamais `middleware.ts` — cf. `admin/layout.tsx`) ; `/acces` et `/benevoles` restent hors du groupe.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, pytest (backend) ; Next.js 16 App Router, TypeScript, Vitest + RTL (frontend).

**Spec:** `docs/superpowers/specs/2026-08-20-mot-de-passe-site-design.md`

## Global Constraints

- Secret distinct du mot de passe bénévoles ; aucun compte système « anonyme », aucun rattachement RBAC spéculatif.
- Mot de passe administrable depuis le back-office (pas de variable d'environnement).
- Garde posée **et** côté backend (tous les routers sauf 3 exceptions nommées), **et** côté frontend (layout, jamais middleware).
- Expiration serveur à 7 jours (`SITE_ACCESS_SESSION_TTL_DAYS`), sans renouvellement glissant.
- `/benevoles` (#271) et `/acces` restent hors de la garde site — populations et rôles distincts.
- `tests/conftest.py::client` neutralise `require_site_access` par défaut (`dependency_overrides`) — pas de ligne `site_access_config` ni de cookie à fabriquer dans les ~745 tests existants.
- Aucune dépendance ajoutée sur l'objet `APIRouter` d'un module existant (`module.router.dependencies` reste `[]`) — la garde se pose à l'inclusion (`include_router(..., dependencies=[...])`), jamais sur le router lui-même.

---

## Task 1: `services/shared_password.py` — factoriser le HMAC et le hachage scrypt

**Files:**
- Create: `backend/app/services/shared_password.py`
- Modify: `backend/app/services/benevole_access.py`
- Test: `backend/tests/test_services/test_shared_password.py`

**Interfaces:**
- Produces: `sign_cookie(key: str) -> str`, `verify_cookie(value: str | None, key: str, *, max_age_seconds: int | None = None) -> bool`, `hash_password(password: str) -> tuple[str, str]`, `verify_password(password: str, *, password_hash: str, password_salt: str) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_services/test_shared_password.py
"""Socle HMAC + scrypt partagé par benevole_access (#271) et site_access (#509)."""
import time

from app.services import shared_password


def test_round_trip_avec_la_meme_cle():
    valeur = shared_password.sign_cookie("secret")
    assert shared_password.verify_cookie(valeur, "secret") is True


def test_echoue_si_la_cle_a_change():
    valeur = shared_password.sign_cookie("ancien-secret")
    assert shared_password.verify_cookie(valeur, "nouveau-secret") is False


def test_echoue_sur_une_valeur_vide_ou_mal_formee():
    assert shared_password.verify_cookie(None, "secret") is False
    assert shared_password.verify_cookie("", "secret") is False
    assert shared_password.verify_cookie("sans-point", "secret") is False


def test_echoue_si_aucune_cle_n_est_configuree():
    valeur = shared_password.sign_cookie("secret")
    assert shared_password.verify_cookie(valeur, "") is False


def test_sans_max_age_une_valeur_ancienne_reste_valide():
    horodatage = str(int(time.time()) - 999_999)
    signature = shared_password._hmac("secret", horodatage)
    valeur = f"{horodatage}.{signature}"
    assert shared_password.verify_cookie(valeur, "secret") is True


def test_avec_max_age_une_valeur_trop_ancienne_est_refusee():
    horodatage = str(int(time.time()) - 100)
    signature = shared_password._hmac("secret", horodatage)
    valeur = f"{horodatage}.{signature}"
    assert shared_password.verify_cookie(valeur, "secret", max_age_seconds=50) is False


def test_avec_max_age_une_valeur_recente_reste_valide():
    valeur = shared_password.sign_cookie("secret")
    assert shared_password.verify_cookie(valeur, "secret", max_age_seconds=3600) is True


def test_avec_max_age_un_horodatage_non_numerique_est_refuse():
    valeur = f"pas-un-nombre.{shared_password._hmac('secret', 'pas-un-nombre')}"
    assert shared_password.verify_cookie(valeur, "secret", max_age_seconds=3600) is False


def test_hash_password_accepte_le_bon_mot_de_passe():
    password_hash, password_salt = shared_password.hash_password("secret-du-club")
    assert shared_password.verify_password(
        "secret-du-club", password_hash=password_hash, password_salt=password_salt
    )


def test_hash_password_rejette_un_mauvais_mot_de_passe():
    password_hash, password_salt = shared_password.hash_password("secret-du-club")
    assert not shared_password.verify_password(
        "autre-mot-de-passe", password_hash=password_hash, password_salt=password_salt
    )


def test_hash_password_produit_un_sel_different_a_chaque_appel():
    premier_hash, premier_sel = shared_password.hash_password("secret-du-club")
    second_hash, second_sel = shared_password.hash_password("secret-du-club")
    assert premier_sel != second_sel
    assert premier_hash != second_hash
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/test_services/test_shared_password.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.shared_password'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/shared_password.py
"""HMAC de cookie et hachage de mot de passe — socle partagé par les deux
mots de passe communs du dépôt (`benevole_access`, #271 ; `site_access`,
#509). Les deux diffèrent par leur cookie, leur table et leur politique
d'expiration — jamais par ce calcul.
"""
import hashlib
import hmac
import secrets
import time

_SALT_SIZE = 16


def sign_cookie(key: str) -> str:
    """`{horodatage}.{HMAC(key, horodatage)}` — sans état serveur à la vérification."""
    horodatage = str(int(time.time()))
    return f"{horodatage}.{_hmac(key, horodatage)}"


def verify_cookie(value: str | None, key: str, *, max_age_seconds: int | None = None) -> bool:
    """Vrai si `value` a été signée par `key`, et — si `max_age_seconds` est
    fourni — émise il y a moins de ce délai. Fail-closed sur toute forme
    inattendue : valeur/clé absente, horodatage non numérique, signature
    fausse rendent tous `False`, jamais une exception.
    """
    if not value or not key:
        return False
    horodatage, separateur, signature = value.partition(".")
    if not separateur or not horodatage or not signature:
        return False
    if not hmac.compare_digest(signature, _hmac(key, horodatage)):
        return False
    if max_age_seconds is None:
        return True
    try:
        emis = int(horodatage)
    except ValueError:
        return False
    return time.time() - emis <= max_age_seconds


def _hmac(key: str, message: str) -> str:
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str) -> tuple[str, str]:
    """`(password_hash, password_salt)`, hexadécimaux. `hashlib.scrypt`
    (memory-hard) plutôt qu'un SHA-256 salé : un mot de passe choisi par un
    humain a une entropie bien inférieure à un jeton généré. Sel de 16
    octets, régénéré à chaque appel.
    """
    salt = secrets.token_bytes(_SALT_SIZE)
    empreinte = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return empreinte.hex(), salt.hex()


def verify_password(password: str, *, password_hash: str, password_salt: str) -> bool:
    """Comparaison en temps constant, même patron que `verify_cookie`."""
    empreinte = hashlib.scrypt(
        password.encode("utf-8"), salt=bytes.fromhex(password_salt), n=2**14, r=8, p=1
    )
    return hmac.compare_digest(empreinte.hex(), password_hash)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_shared_password.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Point `benevole_access.py` at the shared module**

Replace the HMAC/scrypt bodies in `backend/app/services/benevole_access.py` with thin delegations — **keep the public function names and signatures identical** so every existing caller (`api/deps.py`, `api/v1/benevoles.py`, `api/v1/admin_benevole_access.py`, all benevole tests) needs zero changes:

```python
# In backend/app/services/benevole_access.py — replace sign_session,
# verify_session, _hmac, hash_password, verify_password with:
from app.services import shared_password


def sign_session(key: str) -> str:
    return shared_password.sign_cookie(key)


def verify_session(value: str | None, key: str) -> bool:
    return shared_password.verify_cookie(value, key)


def hash_password(password: str) -> tuple[str, str]:
    return shared_password.hash_password(password)


def verify_password(password: str, *, password_hash: str, password_salt: str) -> bool:
    return shared_password.verify_password(
        password, password_hash=password_hash, password_salt=password_salt
    )
```

Remove the now-unused `import hashlib`, `import hmac` from the top of the file if nothing else in it uses them (`secrets` stays — `new_session_secret`/`generate_password` still use it).

- [ ] **Step 6: Run the full benevole test suite to confirm no regression**

Run: `uv run pytest tests/test_services/test_benevole_access.py tests/test_api/test_benevoles_api.py tests/test_auth/test_admin_benevole_access_api.py -v`
Expected: PASS, unchanged — these tests call `benevole_access.sign_session`/`verify_session`/`hash_password`/`verify_password` by the same names, now delegating internally.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/shared_password.py backend/app/services/benevole_access.py backend/tests/test_services/test_shared_password.py
git commit -m "refactor(auth): factorise le HMAC et le hachage scrypt dans shared_password"
```

---

## Task 2: `SiteAccessConfig` — modèle, migration, repository

**Files:**
- Create: `backend/app/models/site_access_config.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/repositories/site_access_config_repository.py`
- Create: `backend/alembic/versions/<auto>_site_access_config_table.py` (généré par Alembic)
- Test: `backend/tests/test_repositories/test_site_access_config_repository.py`

**Interfaces:**
- Produces: `SiteAccessConfig` model (`id`, `password_hash`, `password_salt`, `session_secret`, `updated_at`, `updated_by_user_id`, `updated_by` relationship) ; `site_access_config_repository.get_config(db) -> SiteAccessConfig | None`, `.save_config(db, *, password_hash, password_salt, session_secret, updated_by_user_id) -> SiteAccessConfig`, `.SINGLETON_ID = 1`.

- [ ] **Step 1: Write the failing repository tests**

```python
# backend/tests/test_repositories/test_site_access_config_repository.py
"""SiteAccessConfig — une seule ligne à tout instant, distincte de
`benevole_access_config` (#271) : même contrat, deux secrets indépendants."""
from app.repositories import site_access_config_repository, user_repository


def test_get_config_rend_none_en_l_absence_de_configuration(db_session):
    assert site_access_config_repository.get_config(db_session) is None


def test_save_config_cree_la_ligne_absente(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config = site_access_config_repository.save_config(
        db_session,
        password_hash="hash",
        password_salt="salt",
        session_secret="secret",
        updated_by_user_id=admin.id,
    )

    assert config.id is not None
    releve = site_access_config_repository.get_config(db_session)
    assert releve.id == config.id
    assert releve.updated_by.id == admin.id


def test_save_config_met_a_jour_la_ligne_existante_sans_en_creer_une_seconde(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    premiere = site_access_config_repository.save_config(
        db_session,
        password_hash="hash-1",
        password_salt="salt-1",
        session_secret="secret-1",
        updated_by_user_id=admin.id,
    )
    seconde = site_access_config_repository.save_config(
        db_session,
        password_hash="hash-2",
        password_salt="salt-2",
        session_secret="secret-2",
        updated_by_user_id=admin.id,
    )

    assert seconde.id == premiere.id
    releve = site_access_config_repository.get_config(db_session)
    assert releve.password_hash == "hash-2"
    assert releve.session_secret == "secret-2"


def test_save_config_ne_cree_pas_une_seconde_ligne_face_a_une_ecriture_concurrente(db_session):
    from app.models.site_access_config import SiteAccessConfig

    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    db_session.add(
        SiteAccessConfig(
            id=site_access_config_repository.SINGLETON_ID,
            password_hash="hash-concurrent",
            password_salt="salt-concurrent",
            session_secret="secret-concurrent",
            updated_by_user_id=admin.id,
        )
    )
    db_session.flush()

    config = site_access_config_repository.save_config(
        db_session,
        password_hash="hash-apres",
        password_salt="salt-apres",
        session_secret="secret-apres",
        updated_by_user_id=admin.id,
    )

    assert config.id == site_access_config_repository.SINGLETON_ID
    assert db_session.query(SiteAccessConfig).count() == 1
    assert config.password_hash == "hash-apres"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_repositories/test_site_access_config_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.site_access_config'`

- [ ] **Step 3: Write the model**

```python
# backend/app/models/site_access_config.py
"""SiteAccessConfig — mot de passe partagé fermant l'accès public au site
(#509). Même schéma que `BenevoleAccessConfig` (#271), table distincte :
les deux secrets tournent indépendamment, deux populations différentes.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class SiteAccessConfig(Base):
    """État courant du mot de passe partagé du site. Une seule ligne existe
    à tout instant ; absence de ligne = accès non configuré (fail-closed).
    """

    __tablename__ = "site_access_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    password_salt: Mapped[str] = mapped_column(String, nullable=False)
    session_secret: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    updated_by: Mapped["User"] = relationship()  # noqa: F821
```

Add it to `backend/app/models/__init__.py`, mirroring the existing `BenevoleAccessConfig` entries (an import line and an `__all__`/tuple entry — copy the exact two-line pattern already used for `BenevoleAccessConfig`).

- [ ] **Step 4: Write the repository**

```python
# backend/app/repositories/site_access_config_repository.py
"""Accès données pour SiteAccessConfig — seule couche qui touche la Session.

Patron identique à `benevole_config_repository.py` : une seule ligne existe
à tout instant, `save_config` écrit la ligne existante ou la crée. Ne
commite jamais — la transaction reste portée par le service appelant.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.site_access_config import SiteAccessConfig

SINGLETON_ID = 1


def get_config(db: Session) -> SiteAccessConfig | None:
    return db.scalar(
        select(SiteAccessConfig).options(joinedload(SiteAccessConfig.updated_by))
    )


def save_config(
    db: Session,
    *,
    password_hash: str,
    password_salt: str,
    session_secret: str,
    updated_by_user_id: int,
) -> SiteAccessConfig:
    config = db.get(SiteAccessConfig, SINGLETON_ID)
    if config is not None:
        config.password_hash = password_hash
        config.password_salt = password_salt
        config.session_secret = session_secret
        config.updated_by_user_id = updated_by_user_id
        db.flush()
        db.refresh(config)
        return config

    config = SiteAccessConfig(
        id=SINGLETON_ID,
        password_hash=password_hash,
        password_salt=password_salt,
        session_secret=session_secret,
        updated_by_user_id=updated_by_user_id,
    )
    try:
        with db.begin_nested():
            db.add(config)
            db.flush()
    except IntegrityError:
        config = db.get(SiteAccessConfig, SINGLETON_ID)
        if config is None:  # pragma: no cover
            raise
        config.password_hash = password_hash
        config.password_salt = password_salt
        config.session_secret = session_secret
        config.updated_by_user_id = updated_by_user_id
        db.flush()
    db.refresh(config)
    return config
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_repositories/test_site_access_config_repository.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Generate and review the migration**

Run: `uv run alembic revision --autogenerate -m "site access config table"`

Open the generated file under `backend/alembic/versions/` and confirm `upgrade()` matches (adjust column order/types to match exactly):

```python
def upgrade() -> None:
    op.create_table(
        "site_access_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("password_salt", sa.String(), nullable=False),
        sa.Column("session_secret", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("site_access_config")
```

- [ ] **Step 7: Apply the migration locally**

Run: `uv run alembic upgrade head`
Expected: applies cleanly, `uv run alembic heads` shows a single head.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/site_access_config.py backend/app/models/__init__.py backend/app/repositories/site_access_config_repository.py backend/alembic/versions/ backend/tests/test_repositories/test_site_access_config_repository.py
git commit -m "feat(auth): ajoute le modèle et le repository SiteAccessConfig (#509)"
```

---

## Task 3: `services/site_access.py` — orchestration métier

**Files:**
- Create: `backend/app/services/site_access.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_services/test_site_access.py`

**Interfaces:**
- Consumes: `shared_password.{sign_cookie,verify_cookie,hash_password,verify_password}` (Task 1), `site_access_config_repository.save_config` (Task 2).
- Produces: `SITE_SESSION_COOKIE = "tcn_site_session"`, `sign_session(key) -> str`, `verify_session(value, key, *, max_age_seconds) -> bool`, `new_session_secret() -> str`, `generate_password() -> str`, `verify_password(password, *, password_hash, password_salt) -> bool`, `replace_password(db, *, password, admin_user_id) -> tuple[SiteAccessConfig, str]`. `Settings.site_access_session_ttl_days: int` (default 7).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_services/test_site_access.py
"""Mot de passe partagé fermant l'accès public au site (#509)."""
from app.repositories import user_repository
from app.services import site_access


def test_new_session_secret_rend_une_valeur_differente_a_chaque_appel():
    assert site_access.new_session_secret() != site_access.new_session_secret()


def test_generate_password_rend_une_valeur_suffisamment_longue_et_variable():
    premier = site_access.generate_password()
    second = site_access.generate_password()
    assert premier != second
    assert len(premier) >= 20


def test_verify_session_respecte_le_ttl():
    valeur = site_access.sign_session("secret-du-site")
    assert site_access.verify_session(valeur, "secret-du-site", max_age_seconds=3600) is True
    assert site_access.verify_session(valeur, "secret-du-site", max_age_seconds=0) is False


def test_verify_password_accepte_le_bon_mot_de_passe():
    password_hash, password_salt = site_access.hash_password("mot-de-passe-club")
    assert site_access.verify_password(
        "mot-de-passe-club", password_hash=password_hash, password_salt=password_salt
    )


def test_replace_password_avec_saisie_stocke_le_hash_et_pas_le_mot_de_passe(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config, mot_de_passe = site_access.replace_password(
        db_session, password="mon-nouveau-secret", admin_user_id=admin.id
    )

    assert mot_de_passe == "mon-nouveau-secret"
    assert config.password_hash != "mon-nouveau-secret"
    assert site_access.verify_password(
        "mon-nouveau-secret",
        password_hash=config.password_hash,
        password_salt=config.password_salt,
    )


def test_replace_password_sans_saisie_genere_un_mot_de_passe(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    config, mot_de_passe = site_access.replace_password(
        db_session, password=None, admin_user_id=admin.id
    )

    assert len(mot_de_passe) >= 20
    assert site_access.verify_password(
        mot_de_passe, password_hash=config.password_hash, password_salt=config.password_salt
    )


def test_replace_password_regenere_le_secret_de_session(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()

    premiere_config, _ = site_access.replace_password(
        db_session, password="premier-secret", admin_user_id=admin.id
    )
    ancien_secret = premiere_config.session_secret

    seconde_config, _ = site_access.replace_password(
        db_session, password="second-secret", admin_user_id=admin.id
    )

    assert seconde_config.session_secret != ancien_secret
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_site_access.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.site_access'`

- [ ] **Step 3: Add the TTL setting**

In `backend/app/core/config.py`, add near the other feature settings (after the PostHog block, before the batches block, or any clearly-separated spot):

```python
    # ── Mot de passe d'accès au site (#509) ───────────────────────────────────
    # Expiration serveur du cookie `tcn_site_session`, vérifiée dans le jeton
    # signé lui-même (research.md — pas de renouvellement glissant pour ce
    # premier livrable, même patron que `auth_session_ttl_days`).
    site_access_session_ttl_days: int = 7
```

- [ ] **Step 4: Write the service**

```python
# backend/app/services/site_access.py
"""Mot de passe partagé fermant l'accès public au site entier (#509).

Distinct du mot de passe bénévoles (#271) : secret propre, table propre,
cookie propre — même mécanisme (`services/shared_password`), même contrat
fail-closed. Contrairement à #271, ce cookie porte une expiration serveur
(`Settings.site_access_session_ttl_days`) : #509 la demande explicitement,
là où le cookie bénévoles est un cookie de session navigateur sans `max_age`.
"""
import secrets

from sqlalchemy.orm import Session

from app.models.site_access_config import SiteAccessConfig
from app.repositories import site_access_config_repository
from app.services import shared_password

SITE_SESSION_COOKIE = "tcn_site_session"

_GENERATED_PASSWORD_SIZE = 18


def sign_session(key: str) -> str:
    return shared_password.sign_cookie(key)


def verify_session(value: str | None, key: str, *, max_age_seconds: int) -> bool:
    return shared_password.verify_cookie(value, key, max_age_seconds=max_age_seconds)


def hash_password(password: str) -> tuple[str, str]:
    return shared_password.hash_password(password)


def verify_password(password: str, *, password_hash: str, password_salt: str) -> bool:
    return shared_password.verify_password(
        password, password_hash=password_hash, password_salt=password_salt
    )


def new_session_secret() -> str:
    return secrets.token_urlsafe(32)


def generate_password() -> str:
    """144 bits d'entropie (`secrets.token_urlsafe(18)`) — trop pour un
    humain à retenir, ce qui est le but d'une génération côté serveur."""
    return secrets.token_urlsafe(_GENERATED_PASSWORD_SIZE)


def replace_password(
    db: Session, *, password: str | None, admin_user_id: int
) -> tuple[SiteAccessConfig, str]:
    """Remplace le mot de passe — saisi ou généré. Rend `(config,
    mot_de_passe_en_clair)`. Hache le mot de passe, régénère
    `session_secret`, écrit les trois champs **ensemble** — jamais l'un sans
    les autres, sous peine de casser soit la vérification soit l'invalidation
    des sessions ouvertes.
    """
    mot_de_passe = password if password is not None else generate_password()
    password_hash, password_salt = hash_password(mot_de_passe)
    config = site_access_config_repository.save_config(
        db,
        password_hash=password_hash,
        password_salt=password_salt,
        session_secret=new_session_secret(),
        updated_by_user_id=admin_user_id,
    )
    return config, mot_de_passe
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_site_access.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/site_access.py backend/app/core/config.py backend/tests/test_services/test_site_access.py
git commit -m "feat(auth): service site_access — mot de passe et session (#509)"
```

---

## Task 4: `require_site_access` — la garde

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/test_api/test_require_site_access.py`

**Interfaces:**
- Consumes: `site_access_config_repository.get_config` (Task 2), `site_access.{SITE_SESSION_COOKIE,verify_session}` (Task 3), `Settings.site_access_session_ttl_days` (Task 3).
- Produces: `require_site_access(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> None` — raises `NotAuthenticatedError` (401) on failure.

- [ ] **Step 1: Write the failing tests**

Mirror `tests/test_api/test_benevoles_api.py`'s isolated-app pattern exactly:

```python
# backend/tests/test_api/test_require_site_access.py
"""Garde `require_site_access` (#509), isolée sur une application jetable —
patron `test_benevoles_api.py::application`/`visiteur`."""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_site_access
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.repositories import user_repository
from app.services import site_access

MOT_DE_PASSE_TTL_JOURS = 7


@pytest.fixture
def administrateur(db_session):
    compte = user_repository.create(
        db_session, email="admin-test@exemple.fr", display_name="Admin Test"
    )
    db_session.flush()
    return compte


@pytest.fixture(autouse=True)
def mot_de_passe_configure(db_session, administrateur):
    site_access.replace_password(db_session, password="secret-du-site", admin_user_id=administrateur.id)
    db_session.commit()


@pytest.fixture
def application(db_session) -> FastAPI:
    api = FastAPI()
    register_exception_handlers(api)

    @api.get("/protege", dependencies=[Depends(require_site_access)])
    def protege():
        return {"ok": True}

    def _get_db():
        yield db_session

    api.dependency_overrides[get_db] = _get_db
    return api


@pytest.fixture
def visiteur(application) -> TestClient:
    with TestClient(application) as client:
        yield client


def test_refuse_sans_cookie(visiteur):
    assert visiteur.get("/protege").status_code == 401


def test_refuse_avec_un_cookie_invalide(visiteur):
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, "n-importe-quoi")
    assert visiteur.get("/protege").status_code == 401


def test_refuse_meme_avec_un_cookie_signe_par_un_autre_secret(visiteur):
    valeur = site_access.sign_session("autre-secret-de-session")
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 401


def test_accepte_un_cookie_valide(db_session, visiteur):
    from app.repositories import site_access_config_repository

    config = site_access_config_repository.get_config(db_session)
    valeur = site_access.sign_session(config.session_secret)
    visiteur.cookies.set(site_access.SITE_SESSION_COOKIE, valeur)
    assert visiteur.get("/protege").status_code == 200


def test_refuse_sans_configuration(db_session, visiteur):
    from app.models.site_access_config import SiteAccessConfig

    db_session.query(SiteAccessConfig).delete()
    db_session.commit()
    assert visiteur.get("/protege").status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_require_site_access.py -v`
Expected: FAIL — `ImportError: cannot import name 'require_site_access'`

- [ ] **Step 3: Implement the guard**

In `backend/app/api/deps.py`, add the import and the dependency, right after `require_benevole_access`:

```python
from app.repositories import benevole_config_repository, site_access_config_repository
from app.services import benevole_access, site_access
```

```python
def require_site_access(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> None:
    """Garde transverse du site entier (#509) — mot de passe partagé, pas de
    RBAC. Distincte de `require_benevole_access` : secret et cookie propres.
    Fail-closed : configuration absente, cookie absent/invalide/expiré
    rendent tous le même 401.
    """
    config = site_access_config_repository.get_config(db)
    cookie = request.cookies.get(site_access.SITE_SESSION_COOKIE)
    ttl_seconds = settings.site_access_session_ttl_days * 24 * 60 * 60
    if config is None or not site_access.verify_session(
        cookie, config.session_secret, max_age_seconds=ttl_seconds
    ):
        raise NotAuthenticatedError()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_require_site_access.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_api/test_require_site_access.py
git commit -m "feat(auth): garde require_site_access (#509)"
```

---

## Task 5: Routeur `site_access` — ouverture/fermeture/vérification de session

**Files:**
- Create: `backend/app/schemas/site_access.py`
- Create: `backend/app/api/v1/site_access.py`
- Test: `backend/tests/test_api/test_site_access_api.py`

**Interfaces:**
- Consumes: `site_access_config_repository.get_config` (Task 2), `site_access.{SITE_SESSION_COOKIE,sign_session,verify_password}` (Task 3), `require_site_access` (Task 4).
- Produces: `router` (APIRouter) with `POST /site-access/session`, `DELETE /site-access/session`, `GET /site-access/session`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_api/test_site_access_api.py
"""Ouverture/fermeture/vérification de la session site (#509)."""
import pytest

from app.repositories import user_repository
from app.services import site_access

MOT_DE_PASSE = "secret-du-club"


@pytest.fixture
def administrateur(db_session):
    compte = user_repository.create(
        db_session, email="admin-test@exemple.fr", display_name="Admin Test"
    )
    db_session.flush()
    return compte


@pytest.fixture(autouse=True)
def mot_de_passe_configure(db_session, administrateur):
    site_access.replace_password(db_session, password=MOT_DE_PASSE, admin_user_id=administrateur.id)
    db_session.commit()


def _client_anonyme(client):
    """`client` neutralise `require_site_access` par défaut (Task 8) — ce
    fichier teste précisément ce mécanisme, il le retire."""
    from app.api.deps import require_site_access
    from app.main import app

    app.dependency_overrides.pop(require_site_access, None)
    return client


def test_ouvre_une_session_avec_le_bon_mot_de_passe(client):
    reponse = _client_anonyme(client).post("/api/v1/site-access/session", json={"password": MOT_DE_PASSE})
    assert reponse.status_code == 204
    assert site_access.SITE_SESSION_COOKIE in reponse.cookies


def test_refuse_un_mauvais_mot_de_passe(client):
    reponse = _client_anonyme(client).post(
        "/api/v1/site-access/session", json={"password": "mauvais-mot-de-passe"}
    )
    assert reponse.status_code == 401
    assert site_access.SITE_SESSION_COOKIE not in reponse.cookies


def test_ferme_la_session(client):
    c = _client_anonyme(client)
    c.post("/api/v1/site-access/session", json={"password": MOT_DE_PASSE})
    reponse = c.delete("/api/v1/site-access/session")
    assert reponse.status_code == 204


def test_verification_refuse_sans_cookie(client):
    reponse = _client_anonyme(client).get("/api/v1/site-access/session")
    assert reponse.status_code == 401


def test_verification_accepte_apres_ouverture(client):
    c = _client_anonyme(client)
    c.post("/api/v1/site-access/session", json={"password": MOT_DE_PASSE})
    reponse = c.get("/api/v1/site-access/session")
    assert reponse.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_site_access_api.py -v`
Expected: FAIL — `404` (route not registered yet)

- [ ] **Step 3: Write the schema**

```python
# backend/app/schemas/site_access.py
"""DTO de l'ouverture de session du mot de passe site (#509)."""
from pydantic import BaseModel


class SiteAccessLogin(BaseModel):
    """Corps de `POST /site-access/session`."""

    password: str
```

- [ ] **Step 4: Write the router**

```python
# backend/app/api/v1/site_access.py
"""Session du mot de passe partagé du site (#509).

Couche mince : `require_site_access` (`api/deps.py`) garde la vérification,
elle-même **auto-appliquée** ici sur `GET /site-access/session` — c'est le
point que le frontend interroge pour savoir s'il doit rediriger vers
`/acces`. `POST`/`DELETE` restent non gardées : la première pose le cookie,
la seconde n'a aucun effet de bord sensible.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import NotAuthenticatedError, require_site_access
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.repositories import site_access_config_repository
from app.schemas.site_access import SiteAccessLogin
from app.services import site_access

router = APIRouter(tags=["site-access"])


@router.post("/site-access/session", status_code=204)
def open_session(
    body: SiteAccessLogin,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    config = site_access_config_repository.get_config(db)
    if config is None or not site_access.verify_password(
        body.password, password_hash=config.password_hash, password_salt=config.password_salt
    ):
        raise NotAuthenticatedError("Mot de passe incorrect.")

    response.set_cookie(
        key=site_access.SITE_SESSION_COOKIE,
        value=site_access.sign_session(config.session_secret),
        max_age=settings.site_access_session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.delete("/site-access/session", status_code=204)
def close_session(response: Response, settings: Settings = Depends(get_settings)):
    response.delete_cookie(
        key=site_access.SITE_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get("/site-access/session", dependencies=[Depends(require_site_access)])
def check_session():
    """Le frontend l'appelle via `serverFetchAuthed` : 200 si la session est
    valide, 401 sinon (levé par `require_site_access` avant d'atteindre ce corps)."""
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_site_access_api.py -v`
Expected: still FAIL — the router isn't mounted yet (Task 8 wires `v1/router.py`). Confirm the failure is now 404 rather than an import/collection error, then proceed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/site_access.py backend/app/api/v1/site_access.py backend/tests/test_api/test_site_access_api.py
git commit -m "feat(auth): routeur site_access — session (#509)"
```

(This task's tests turn green once Task 8 mounts the router — that's expected and checked there.)

---

## Task 6: Pouvoir RBAC `site_access:manage`

**Files:**
- Modify: `backend/app/core/permissions.py`

**Interfaces:**
- Produces: `P.SITE_ACCESS_MANAGE` (code `"site_access:manage"`), added to `ALL`.

- [ ] **Step 1: Add the permission**

In `backend/app/core/permissions.py`, inside class `P`, right after `BENEVOLE_ACCESS_MANAGE`:

```python
    SITE_ACCESS_MANAGE = Permission(
        "site_access:manage",
        "Gérer l'accès au site",
        "Consulter l'état du mot de passe partagé du site, le remplacer par "
        "une saisie ou en générer un nouveau de façon sécurisée.",
        FEATURE_ROLES,
    )
```

And in the `ALL` tuple, right after `P.BENEVOLE_ACCESS_MANAGE,`:

```python
    P.SITE_ACCESS_MANAGE,
```

- [ ] **Step 2: Run the catalogue guard test — expect a named failure**

Run: `uv run pytest tests/test_permissions_catalogue.py -v`
Expected: FAIL on `test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource[site_access:manage]` — the code exists but nothing guards it yet. This is the expected red state; Task 7 turns it green.

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/permissions.py
git commit -m "feat(auth): pouvoir site_access:manage (#509)"
```

---

## Task 7: Administration du mot de passe site

**Files:**
- Create: `backend/app/schemas/site_access_config.py`
- Create: `backend/app/api/v1/admin_site_access.py`
- Test: `backend/tests/test_auth/test_admin_site_access_api.py`

**Interfaces:**
- Consumes: `require_permission(P.SITE_ACCESS_MANAGE)` (Task 6), `site_access.replace_password` (Task 3), `admin_action_log_repository.create`.
- Produces: `GET/PUT /admin/site-access`, `POST /admin/site-access/generate`.

- [ ] **Step 1: Write the failing tests**

`tests/test_auth/conftest.py` already provides `ouvrir_session(*codes, nom=...)` — it opens a real SSO session carrying exactly the permission codes given, and lives alongside this new file so no import is needed:

```python
# backend/tests/test_auth/test_admin_site_access_api.py
"""Gestion admin du mot de passe partagé du site (#509) — patron exact de
test_admin_benevole_access_api.py, RBAC (`site_access:manage`)."""
from app.core.permissions import P

URL = "/api/v1/admin/site-access"
URL_GENERATE = f"{URL}/generate"


def test_get_sans_session_est_refuse(client):
    assert client.get(URL).status_code == 401


def test_get_sans_le_pouvoir_est_refuse(client, ouvrir_session):
    ouvrir_session()  # aucun pouvoir
    assert client.get(URL).status_code == 403


def test_get_rend_non_configure_avant_tout_reglage(client, ouvrir_session):
    ouvrir_session(P.SITE_ACCESS_MANAGE)
    reponse = client.get(URL)
    assert reponse.status_code == 200
    assert reponse.json() == {"configured": False, "updated_at": None, "updated_by": None}


def test_put_remplace_le_mot_de_passe(client, ouvrir_session):
    ouvrir_session(P.SITE_ACCESS_MANAGE, nom="Iris Admin")
    reponse = client.put(URL, json={"password": "un-secret-assez-long"})
    assert reponse.status_code == 200
    charge = reponse.json()
    assert charge["configured"] is True
    assert charge["updated_by"] == "Iris Admin"


def test_generate_rend_le_mot_de_passe_en_clair_une_seule_fois(client, ouvrir_session):
    ouvrir_session(P.SITE_ACCESS_MANAGE)
    reponse = client.post(URL_GENERATE)
    assert reponse.status_code == 200
    assert len(reponse.json()["password"]) >= 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth/test_admin_site_access_api.py -v`
Expected: FAIL — 404 (route not yet defined)

- [ ] **Step 3: Write the schema**

```python
# backend/app/schemas/site_access_config.py
"""DTO de la gestion admin du mot de passe partagé du site (#509)."""
from datetime import datetime

from pydantic import BaseModel, Field


class SiteAccessConfigOut(BaseModel):
    configured: bool
    updated_at: datetime | None = None
    updated_by: str | None = None


class SiteAccessReplaceIn(BaseModel):
    password: str = Field(min_length=8)


class SiteAccessGeneratedOut(BaseModel):
    password: str
    updated_at: datetime
    updated_by: str
```

- [ ] **Step 4: Write the router**

```python
# backend/app/api/v1/admin_site_access.py
"""Gestion admin du mot de passe partagé du site (#509) — patron exact de
`admin_benevole_access.py`."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import admin_action_log_repository, site_access_config_repository
from app.schemas.site_access_config import (
    SiteAccessConfigOut,
    SiteAccessGeneratedOut,
    SiteAccessReplaceIn,
)
from app.services import site_access

router = APIRouter(tags=["admin"])

_ENTITY_TYPE = "site_access_config"
_ACTION = "site_access.password_replace"


def _vue(config) -> SiteAccessConfigOut:
    return SiteAccessConfigOut(
        configured=config is not None,
        updated_at=config.updated_at if config else None,
        updated_by=config.updated_by.display_name if config else None,
    )


@router.get("/admin/site-access", response_model=SiteAccessConfigOut)
def get_access_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.SITE_ACCESS_MANAGE)),
):
    return _vue(site_access_config_repository.get_config(db))


@router.put("/admin/site-access", response_model=SiteAccessConfigOut)
def replace_access_password(
    body: SiteAccessReplaceIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.SITE_ACCESS_MANAGE)),
):
    config, _mot_de_passe = site_access.replace_password(
        db, password=body.password, admin_user_id=actor.id
    )
    admin_action_log_repository.create(
        db, user_id=actor.id, action=_ACTION, entity_type=_ENTITY_TYPE, entity_id=config.id
    )
    db.commit()
    return _vue(config)


@router.post("/admin/site-access/generate", response_model=SiteAccessGeneratedOut)
def generate_access_password(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.SITE_ACCESS_MANAGE)),
):
    config, mot_de_passe = site_access.replace_password(db, password=None, admin_user_id=actor.id)
    admin_action_log_repository.create(
        db, user_id=actor.id, action=_ACTION, entity_type=_ENTITY_TYPE, entity_id=config.id
    )
    db.commit()
    return SiteAccessGeneratedOut(
        password=mot_de_passe, updated_at=config.updated_at, updated_by=config.updated_by.display_name
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth/test_admin_site_access_api.py -v`
Expected: still FAIL with 404 until Task 8 mounts the router — confirm the failure mode, then proceed (same situation as Task 5).

- [ ] **Step 6: Run the permissions catalogue guard**

Run: `uv run pytest tests/test_permissions_catalogue.py -v`
Expected: PASS now — `require_permission(P.SITE_ACCESS_MANAGE)` appears three times in `admin_site_access.py`, satisfying `test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/site_access_config.py backend/app/api/v1/admin_site_access.py backend/tests/test_auth/test_admin_site_access_api.py
git commit -m "feat(auth): administration du mot de passe site (#509)"
```

---

## Task 8: Mise en place de la garde transverse et neutralisation de test

**Files:**
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_auth/test_site_access_gate.py` (new)

**Interfaces:**
- Consumes: `require_site_access` (Task 4), `site_access` and `admin_site_access` routers (Tasks 5, 7).
- Produces: every route except `health`, `site_access`, `benevoles` requires `require_site_access` at inclusion time; `client` fixture is anonymous-by-default via `dependency_overrides`.

- [ ] **Step 1: Write the failing gate test**

```python
# backend/tests/test_auth/test_site_access_gate.py
"""La garde transverse du mot de passe site (#509) : tout, sauf trois
exceptions nommées, exige le cookie `tcn_site_session`.

Inventaire dérivé de l'application, comme `test_public_routes_still_open.py`
— jamais tenu à la main.
"""
import pytest

from app.api.deps import require_site_access
from app.main import app
from app.repositories import user_repository
from app.services import site_access

PREFIXE_AUTH = "/api/v1/auth/"

#: Les trois exceptions nommées (design, § Garde backend).
ROUTES_EXEMPTEES_PREFIXES = ("/api/v1/health", "/api/v1/version", "/api/v1/site-access/", "/api/v1/benevoles/")


def _toutes_les_routes() -> list[tuple[str, str]]:
    return [
        (methode.upper(), chemin)
        for chemin, operations in app.openapi()["paths"].items()
        for methode in operations
        if not chemin.startswith(PREFIXE_AUTH)
    ]


def _routes_gardees_par_le_site() -> list[tuple[str, str]]:
    return [
        (methode, chemin)
        for methode, chemin in _toutes_les_routes()
        if not chemin.startswith(ROUTES_EXEMPTEES_PREFIXES)
    ]


def _chemin_concret(chemin: str) -> str:
    return "/".join(
        "1" if morceau.startswith("{") and morceau.endswith("}") else morceau
        for morceau in chemin.split("/")
    )


@pytest.fixture(autouse=True)
def sans_neutralisation(client):
    """Ce fichier éprouve la vraie garde — retire la neutralisation que
    `conftest.py::client` pose par défaut. Dépend explicitement de `client`
    pour s'exécuter **après** elle : deux fixtures sans lien de dépendance
    n'ont aucun ordre garanti entre elles."""
    app.dependency_overrides.pop(require_site_access, None)
    yield


def test_l_inventaire_n_est_pas_vide():
    assert len(_routes_gardees_par_le_site()) >= 10


@pytest.mark.parametrize(
    ("methode", "chemin"),
    _routes_gardees_par_le_site(),
    ids=lambda v: v.replace("/", "_") if isinstance(v, str) else v,
)
def test_toute_route_gardee_refuse_l_anonyme(client, methode, chemin):
    reponse = client.request(methode, _chemin_concret(chemin), json={})
    assert reponse.status_code == 401, f"{methode} {chemin} répond sans le cookie site"


def test_health_repond_sans_cookie(client):
    assert client.get("/api/v1/health").status_code == 200


def test_version_repond_sans_cookie(client):
    assert client.get("/api/v1/version").status_code == 200


def test_benevoles_session_repond_sans_cookie_site(client):
    """La garde site ne ferme pas la page bénévoles : mauvais mot de passe,
    mais pas 401 « pas de cookie site »."""
    reponse = client.post("/api/v1/benevoles/session", json={"password": "n-importe-quoi"})
    assert reponse.status_code == 401  # refus du mot de passe bénévoles, pas de la garde site
    assert not reponse.cookies


def test_une_route_gardee_repond_normalement_avec_le_cookie(client, db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    config, _ = site_access.replace_password(db_session, password="secret-du-club", admin_user_id=admin.id)
    db_session.commit()

    client.cookies.set(site_access.SITE_SESSION_COOKIE, site_access.sign_session(config.session_secret))

    assert client.get("/api/v1/health").status_code == 200  # santé, jamais gardée
    assert client.get("/api/v1/courses").status_code != 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth/test_site_access_gate.py -v`
Expected: FAIL — every parametrized case fails because the guard isn't wired into `v1/router.py` yet (routes respond normally, not 401).

- [ ] **Step 3: Wire the guard into `v1/router.py`**

Replace the single inclusion loop with two, and add the two new modules to the imports:

```python
# backend/app/api/v1/router.py
from fastapi import APIRouter, Depends

from app.api.deps import require_site_access
from app.api.v1 import (
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_benevole_access,
    admin_course_duplicates,
    admin_course_merge,
    admin_course_rescrape,
    admin_course_sources,
    admin_data,
    admin_feedback,
    admin_groups,
    admin_roles,
    admin_sessions,
    admin_site_access,
    athletes,
    auth,
    benevoles,
    courses,
    feedback,
    health,
    participations,
    scrape,
    site_access,
    stats,
)

api_router = APIRouter()

# La garde `require_site_access` (#509) ferme tout, à l'inclusion — jamais sur
# le router lui-même (`module.router.dependencies` reste `[]`, cf.
# `test_aucune_dependance_globale_sur_les_routers_existants`). Trois
# exceptions nommées : `health` (infra), `site_access` (pose le cookie, ne
# peut pas exiger sa propre présence), `benevoles` (#271 — population
# potentiellement non-adhérente, cf. design § Garde backend).
_EXEMPTES_DE_LA_GARDE_SITE = (health, site_access, benevoles)

for module in _EXEMPTES_DE_LA_GARDE_SITE:
    api_router.include_router(module.router)

for module in (
    scrape,
    athletes,
    courses,
    participations,
    stats,
    feedback,
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_benevole_access,
    admin_course_duplicates,
    admin_course_merge,
    admin_course_rescrape,
    admin_course_sources,
    admin_data,
    admin_feedback,
    admin_roles,
    admin_groups,
    admin_sessions,
    admin_site_access,
    auth,
):
    api_router.include_router(module.router, dependencies=[Depends(require_site_access)])
```

- [ ] **Step 4: Neutralize the guard in the shared `client` fixture**

In `backend/tests/conftest.py`:

```python
@pytest.fixture
def client(db_session):
    """TestClient avec `get_db` surchargé pour utiliser la base de test.

    Neutralise aussi `require_site_access` (#509) : la garde s'applique à
    quasiment tous les routers, et la quasi-totalité de la suite ne teste
    pas ce mécanisme — `test_site_access_gate.py` la retire explicitement
    pour l'éprouver.
    """
    from app.api.deps import require_site_access
    from app.core.database import get_db
    from app.main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_site_access] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Run the new gate test to verify it passes**

Run: `uv run pytest tests/test_auth/test_site_access_gate.py -v`
Expected: PASS

- [ ] **Step 6: Run the Task 5 and Task 7 tests — now mounted**

Run: `uv run pytest tests/test_api/test_site_access_api.py tests/test_auth/test_admin_site_access_api.py -v`
Expected: PASS

- [ ] **Step 7: Run the full pre-existing auth/permissions/public-routes suites**

Run: `uv run pytest tests/test_auth/test_public_routes_still_open.py tests/test_permissions_catalogue.py -v`
Expected: PASS, unchanged — `client` now carries the neutralized override, so these files keep exercising only the RBAC axis they always tested. If `test_aucune_dependance_globale_sur_les_routers_existants` fails, it means `dependencies=` was mistakenly added to one of the listed modules' own `APIRouter()` definition rather than at `include_router(...)` — fix the call site, not the test.

- [ ] **Step 8: Run the entire backend suite**

Run: `uv run pytest -m "not integration"`
Expected: PASS, full suite (~750+ tests including the ~9 new ones from Tasks 1-8).

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/v1/router.py backend/tests/conftest.py backend/tests/test_auth/test_site_access_gate.py
git commit -m "feat(auth): pose la garde site sur tous les routers sauf 3 exceptions (#509)"
```

---

## Task 9: Restructuration frontend — groupe de routes `(protege)`

**Files:**
- Move: `frontend/app/{dashboard,resultats,athletes,courses,club,carte,ajouter,admin,login}` → `frontend/app/(protege)/...`

**Interfaces:**
- Produces: every existing route keeps its URL (route groups are invisible in the path) — only the on-disk location changes.

- [ ] **Step 1: Move the directories**

Run from `frontend/`:

```bash
mkdir -p "app/(protege)"
git mv app/dashboard "app/(protege)/dashboard"
git mv app/resultats "app/(protege)/resultats"
git mv app/athletes "app/(protege)/athletes"
git mv app/courses "app/(protege)/courses"
git mv app/club "app/(protege)/club"
git mv app/carte "app/(protege)/carte"
git mv app/ajouter "app/(protege)/ajouter"
git mv app/admin "app/(protege)/admin"
git mv app/login "app/(protege)/login"
```

Leave `app/benevoles`, `app/api`, `app/layout.tsx`, `app/page.tsx`, `app/providers.tsx`, `app/globals.css`, `app/error.tsx` (and any other top-level special file) exactly where they are.

- [ ] **Step 2: Verify the app still builds and routes resolve**

Run: `npm run build`
Expected: succeeds — route groups don't change URLs, and every import in the moved files uses the `@/` alias (never a relative path crossing the moved boundary), so no import needs updating. If the build reports a broken relative import, fix that one import to use the `@/` alias instead of adjusting the move.

- [ ] **Step 3: Run the existing test suite**

Run: `npm test`
Expected: PASS, unchanged — Vitest resolves by `@/` alias and by co-located `*.test.tsx`, neither of which cares about the parenthesized segment.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(frontend): regroupe les routes existantes sous (protege) (#509)"
```

---

## Task 10: Garde frontend `app/(protege)/layout.tsx`

**Files:**
- Create: `frontend/app/(protege)/layout.tsx`
- Modify: `frontend/lib/api/server.ts`

**Interfaces:**
- Consumes: `serverFetchAuthed` pattern already in `lib/api/server.ts`.
- Produces: `apiServer.checkSiteAccess(): Promise<boolean>` ; the layout redirects to `/acces` when it returns `false`.

- [ ] **Step 1: Add `checkSiteAccess` to `apiServer`**

In `frontend/lib/api/server.ts`, add a private call and expose it on `apiServer`:

```typescript
async function serverFetchAuthedRaw(path: string): Promise<boolean> {
  const jar = await cookies();
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: { cookie: jar.toString() },
  });
  return res.ok;
}
```

```typescript
export const apiServer = {
  // ...
  /** Session du mot de passe site (#509) — vrai si le cookie est valide. */
  checkSiteAccess: () => serverFetchAuthedRaw("/site-access/session"),
};
```

- [ ] **Step 2: Write the gate layout**

```tsx
// frontend/app/(protege)/layout.tsx
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { apiServer } from "@/lib/api/server";

/**
 * Garde d'accès au site (#509) — ferme tout ce qui vit sous ce groupe de
 * routes derrière le mot de passe partagé aux adhérents.
 *
 * Un layout, et non `middleware.ts` : même raison que `admin/layout.tsx`
 * (déjà nesté ici) — un middleware ne constate que la présence du cookie,
 * jamais sa validité, et son `matcher` casse facilement les rewrites
 * `/api/*`. Posé sur ce groupe et non sur `app/layout.tsx` : `/acces` et
 * `/benevoles` restent des routes sœurs, jamais soumises à cette garde.
 *
 * Conséquence assumée : toute page de ce groupe devient dynamique — c'est
 * l'effet recherché, au même titre que pour `/admin` avant elle.
 */
export default async function ProtegeLayout({ children }: { children: ReactNode }) {
  const autorise = await apiServer.checkSiteAccess();
  if (!autorise) {
    redirect("/acces");
  }
  return <>{children}</>;
}
```

- [ ] **Step 3: Manual verification**

Run the dev servers (`uv run python scripts/dev_server.py` in `backend/`, `npm run dev` in `frontend/`). With no `site_access_config` row configured yet, visiting `/dashboard` should redirect to `/acces` (Task 11 will make that page functional — for now confirm the redirect happens, e.g. via a 404 on `/acces` is an acceptable interim state).

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(protege)/layout.tsx" frontend/lib/api/server.ts
git commit -m "feat(auth): garde frontend du groupe de routes (protege) (#509)"
```

---

## Task 11: Page `/acces` — formulaire de mot de passe

**Files:**
- Modify: `frontend/lib/api/client.ts`
- Create: `frontend/components/site-access/SiteAccessGate.tsx`
- Create: `frontend/app/acces/page.tsx`
- Test: `frontend/components/site-access/SiteAccessGate.test.tsx`

**Interfaces:**
- Consumes: `apiClient.request` pattern (existing).
- Produces: `apiClient.siteAccessLogin(password: string): Promise<null>`.

- [ ] **Step 1: Write the failing component test**

```tsx
// frontend/components/site-access/SiteAccessGate.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";

const { siteAccessLogin, push } = vi.hoisted(() => ({
  siteAccessLogin: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { siteAccessLogin } };
});

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { SiteAccessGate } from "./SiteAccessGate";

describe("SiteAccessGate", () => {
  beforeEach(() => {
    siteAccessLogin.mockReset();
    push.mockReset();
  });

  it("redirige vers l'accueil après une connexion réussie", async () => {
    siteAccessLogin.mockResolvedValue(null);
    render(<SiteAccessGate />);

    await userEvent.type(screen.getByLabelText(/mot de passe/i), "secret-du-club");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(siteAccessLogin).toHaveBeenCalledWith("secret-du-club");
    expect(push).toHaveBeenCalledWith("/");
  });

  it("affiche une erreur sur un mot de passe refusé", async () => {
    siteAccessLogin.mockRejectedValue(new ApiError(401, "Mot de passe incorrect."));
    render(<SiteAccessGate />);

    await userEvent.type(screen.getByLabelText(/mot de passe/i), "mauvais-mot-de-passe");
    await userEvent.click(screen.getByRole("button", { name: /se connecter/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/mot de passe incorrect/i);
    expect(push).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- SiteAccessGate`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Add the client method**

In `frontend/lib/api/client.ts`, near `benevoleLogin`:

```typescript
  // ── Mot de passe d'accès au site (#509) ────────────────────────────────────
  siteAccessLogin: (password: string) =>
    request<null>("/site-access/session", { method: "POST", body: JSON.stringify({ password }) }),
```

- [ ] **Step 4: Write the component**

```tsx
// frontend/components/site-access/SiteAccessGate.tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Input } from "@/components/tcn";
import { apiClient, ApiError } from "@/lib/api/client";

/** Formulaire du mot de passe partagé au site (#509) — patron `AccessGate` (#271). */
export function SiteAccessGate() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function soumettre(e: React.FormEvent) {
    e.preventDefault();
    setErreur(null);
    setEnCours(true);
    try {
      await apiClient.siteAccessLogin(password);
      router.push("/");
    } catch (err) {
      setErreur(
        err instanceof ApiError ? err.message : "Connexion impossible. Réessayez plus tard.",
      );
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div style={{ maxWidth: 380, margin: "80px auto" }}>
      <Card padding={32}>
        <h1
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: 22,
            color: "var(--tcn-ink)",
            fontWeight: 400,
            margin: 0,
            marginBottom: 8,
          }}
        >
          Accès réservé aux adhérents
        </h1>
        <div style={{ fontSize: 14, color: "var(--tcn-text-faint)", marginBottom: 20 }}>
          Le mot de passe vous a été communiqué par le club.
        </div>
        <form onSubmit={soumettre}>
          <label
            htmlFor="site-password"
            style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--tcn-text-body)" }}
          >
            Mot de passe
          </label>
          <Input
            id="site-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            status={erreur ? "error" : "default"}
            aria-describedby={erreur ? "site-password-erreur" : undefined}
            autoFocus
            style={{ width: "100%" }}
          />
          {erreur && (
            <div id="site-password-erreur" role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>
              {erreur}
            </div>
          )}
          <Button type="submit" disabled={enCours || !password} style={{ width: "100%", marginTop: 16 }}>
            {enCours ? "Connexion…" : "Se connecter"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Write the page**

```tsx
// frontend/app/acces/page.tsx
import { SiteAccessGate } from "@/components/site-access/SiteAccessGate";

export default function AccesPage() {
  return <SiteAccessGate />;
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npm test -- SiteAccessGate`
Expected: PASS (2 tests)

- [ ] **Step 7: Manual verification**

With both dev servers running and no site password configured, `GET /admin/site-access` via `curl` (or the not-yet-built admin screen) can't set one — for this manual check, use the backend CLI/DB directly, or defer full manual verification to after Task 12 lands the admin screen. At minimum, confirm `/acces` renders the form and that submitting a wrong password shows the inline error.

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/api/client.ts frontend/components/site-access frontend/app/acces
git commit -m "feat(auth): page /acces — formulaire du mot de passe site (#509)"
```

---

## Task 12: Écran d'administration du mot de passe site

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/queries/keys.ts`
- Modify: `frontend/lib/queries/admin.ts`
- Create: `frontend/components/admin/SiteAccessConfig.tsx`
- Create: `frontend/components/admin/SiteAccessConfig.test.tsx`
- Modify: `frontend/app/(protege)/admin/acces/page.tsx`

**Interfaces:**
- Produces: `SiteAccessConfig`/`SiteAccessGenerated` types; `apiClient.{getSiteAccessConfig,replaceSiteAccessPassword,generateSiteAccessPassword}`; `useSiteAccessConfig`/`useReplaceSiteAccessPassword`/`useGenerateSiteAccessPassword` hooks; `<SiteAccessConfig />` component mounted on the admin access page.

- [ ] **Step 1: Write the failing component test**

Copy `frontend/components/admin/BenevoleAccessConfig.test.tsx` verbatim into `frontend/components/admin/SiteAccessConfig.test.tsx`, then rename every `Benevole`→`Site`, `benevole`→`site`, `bénévoles`→`site` (the confirmation dialog copy becomes e.g. `/toutes les sessions ouvertes cesseront/i` without the word « bénévoles »), and change the import to `import { SiteAccessConfig } from "./SiteAccessConfig";`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- SiteAccessConfig`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Add types**

In `frontend/lib/types.ts`, near `BenevoleAccessConfig`/`BenevoleAccessGenerated`:

```typescript
/** État courant du mot de passe partagé du site (#509) — jamais le mot de
 * passe ni son empreinte. */
export interface SiteAccessConfig {
  configured: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

/** Réponse de la génération sécurisée — la seule forme qui porte jamais un
 * mot de passe en clair, une seule fois. */
export interface SiteAccessGenerated {
  password: string;
  updated_at: string;
  updated_by: string;
}
```

- [ ] **Step 4: Add client methods**

In `frontend/lib/api/client.ts`, import `SiteAccessConfig, SiteAccessGenerated` alongside the other type imports, then near `generateBenevoleAccessPassword`:

```typescript
  // ── Mot de passe partagé du site (#509) ────────────────────────────────────
  getSiteAccessConfig: () => request<SiteAccessConfig>("/admin/site-access"),
  replaceSiteAccessPassword: (password: string) =>
    request<SiteAccessConfig>("/admin/site-access", { method: "PUT", body: JSON.stringify({ password }) }),
  generateSiteAccessPassword: () =>
    request<SiteAccessGenerated>("/admin/site-access/generate", { method: "POST" }),
```

- [ ] **Step 5: Add the query key**

In `frontend/lib/queries/keys.ts`, next to `benevoleAccessConfig`:

```typescript
  siteAccessConfig: () => ["site-access-config"] as const,
```

- [ ] **Step 6: Add the hooks**

In `frontend/lib/queries/admin.ts`, copy the three `useBenevoleAccessConfig`/`useReplaceBenevoleAccessPassword`/`useGenerateBenevoleAccessPassword` hooks and rename to `useSiteAccessConfig`/`useReplaceSiteAccessPassword`/`useGenerateSiteAccessPassword`, pointing at `apiClient.{getSiteAccessConfig,replaceSiteAccessPassword,generateSiteAccessPassword}` and `queryKeys.siteAccessConfig()`.

- [ ] **Step 7: Write the component**

Copy `frontend/components/admin/BenevoleAccessConfig.tsx`, rename the export to `SiteAccessConfig`, swap the three hook imports for the `useSiteAccess*` ones, change the title to `"Accès au site"`, the description to reference le mot de passe partagé du site plutôt que celui de la page bénévoles, the `REFUS` constant to `{ sujet: "accès au site", action: "gérer l'accès au site" }`, the input id to `site-password`, and the confirmation dialog copy to drop the word « bénévoles » (e.g. « Toutes les sessions ouvertes cesseront immédiatement d'être valides… »).

- [ ] **Step 8: Run tests to verify they pass**

Run: `npm test -- SiteAccessConfig`
Expected: PASS (all cases mirrored from `BenevoleAccessConfig.test.tsx`)

- [ ] **Step 9: Mount it on the admin access page**

```tsx
// frontend/app/(protege)/admin/acces/page.tsx
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { AllowedEmailsTable } from "@/components/admin/AllowedEmailsTable";
import { BenevoleAccessConfig } from "@/components/admin/BenevoleAccessConfig";
import { SiteAccessConfig } from "@/components/admin/SiteAccessConfig";
import { RevokeSessionsCard } from "@/components/admin/RevokeSessionsCard";

export default function AdminAccesPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader
          eyebrow="Gestion des utilisateurs"
          title="Accès au back-office"
          description="Seules ces adresses peuvent ouvrir une session. Une adresse retirée perd l'accès immédiatement."
        />
        <AllowedEmailsTable />
        <SiteAccessConfig />
        <BenevoleAccessConfig />
        <RevokeSessionsCard />
      </div>
    </PageShell>
  );
}
```

- [ ] **Step 10: Full frontend verification**

Run: `npm test` then `npm run build`
Expected: both succeed.

- [ ] **Step 11: Manual end-to-end check**

With both dev servers running: log into `/admin` (needs the site password first, then SSO — set a site password via direct DB/service call if the chicken-and-egg is awkward on a fresh dev DB, e.g. a one-off Python shell calling `site_access.replace_password`), open `/admin/acces`, generate a site password, copy it, open a private/incognito window, visit `/`, confirm redirect to `/acces`, submit the copied password, confirm redirect to `/` and that navigating to `/dashboard`, `/resultats`, etc. no longer redirects. Confirm `/benevoles` remains reachable without the site password (its own gate still applies).

- [ ] **Step 12: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/lib/queries/keys.ts frontend/lib/queries/admin.ts frontend/components/admin/SiteAccessConfig.tsx frontend/components/admin/SiteAccessConfig.test.tsx "frontend/app/(protege)/admin/acces/page.tsx"
git commit -m "feat(auth): écran d'administration du mot de passe site (#509)"
```

---

## Self-Review Notes

- **Spec coverage**: modèle de données (Task 2), mécanisme partagé (Task 1), expiration serveur (Tasks 3-4), garde backend + exceptions nommées (Tasks 4, 8), garde frontend par layout + exceptions (Tasks 9-10), administration (Tasks 6-7, 12), tests (Task 8's gate test + conftest change) — all design sections have a task.
- **Placeholder scan**: every step carries runnable code or an exact shell command; no "add error handling" style steps.
- **Type consistency**: `SITE_SESSION_COOKIE`, `sign_session`/`verify_session` signatures, `SiteAccessConfig`/`SiteAccessGenerated` field names stay identical from their first definition (Task 3/Task 12) through every consumer.
- **Ordering**: Tasks 1-8 (backend) are fully independent of Tasks 9-12 (frontend) except that Task 10's `checkSiteAccess` call targets the Task 5 endpoint — Task 5 must land (even mounted only from Task 8) before Task 10 is manually verified end-to-end. Sequential execution as numbered satisfies this; a parallel executor should hold Task 10 until Task 8 is merged.
