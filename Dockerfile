FROM python:3.12@sha256:a461539b262bcec490d5c7dc0af7b90f204a1851d6d94fcdbb7fad7bd8b9aef6 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:86cd49938a9b50c3663aa93cf5db9c8f498d6fe47f463a2cb967248b9e7d69de

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
