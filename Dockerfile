FROM python:3.12@sha256:1987c4ae3b5afaa3a7c5e247e9eaab7348082ba167986ca90d4d6a197fb364e8 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:eb6d3208444a54418be98f83f1006f6d78ef17144f1cd9eb4e5945d4851af355

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
