# Image API (sans navigateurs Playwright). Le fallback Playwright pourra être isolé dans une
# image dédiée ultérieurement (voir README — Suites).
FROM python:3.13-slim

# uv est copié depuis son image officielle : version épinglée, pas d'installation à la volée.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /bin/

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

# Les dépendances d'abord : cette couche n'est invalidée que si le lock change.
# --frozen : aucune re-résolution silencieuse dans l'image. --no-dev : pas de pytest/ruff en prod.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Le code ensuite : le modifier ne réinstalle pas les dépendances.
COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Le venv du projet sur le PATH : alembic et uvicorn s'appellent sans préfixe.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Applique les migrations puis démarre l'API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
