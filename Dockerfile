# Imagen única del submarino: la misma para app, mcp-tools y worker (cambia el comando).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --uid 10001 glamping
WORKDIR /srv/glamping

COPY requirements.lock ./
COPY pyproject.toml README.md ./
COPY app_core ./app_core
COPY features ./features
COPY docs/prompts ./docs/prompts
COPY docs/spec/esquema.sql ./docs/spec/esquema.sql
COPY scripts ./scripts

# ADR-0021, K2: todo lo que se instala está fijado con hash; el paquete propio no resuelve ni baja nada.
RUN pip install --require-hashes --no-deps -r requirements.lock \
    && pip install --no-deps --no-build-isolation .

USER glamping
EXPOSE 8080
CMD ["uvicorn", "app_core.main:crear_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
