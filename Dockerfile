FROM python:3.12@sha256:fcb0f566de12e4585c8a80a2390337baa51c197f7639eb969eb82b36212ddae3 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:5c73034c2bc151596ee0f1335610735162ee2b148816710706afec4757ad5b1e

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
