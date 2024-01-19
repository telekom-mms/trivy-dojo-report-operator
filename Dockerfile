FROM python:3.12@sha256:7e082bf2ab924afce07aef447111cea2e87c50778ca7b5d7cfbf09692c7e3269 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:a1f70a0d7106954f5c55cb4d70fcdf07c5ee792f71cfeba4f3004ae7f850fd86

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
