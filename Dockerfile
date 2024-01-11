FROM python:3.12@sha256:5a88c14f0f26df7a092edc139bdec35621e8ac11f8c95b38d2a9283bad0cfce1 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:45700299484f0cd248020da669eb55780417c4496444f7c37dfd66e9577dca82

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
