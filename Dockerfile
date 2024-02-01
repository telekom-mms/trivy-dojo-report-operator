FROM python:3.12@sha256:690924bb394da687beb5c2b6a439d556ee6b88659a0a4e0cba7c82c5df7a28d7 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:db7e9284d53f7b827c58a6239b9d2907c33250215823b1cdb7d1e983e70dafa5

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
