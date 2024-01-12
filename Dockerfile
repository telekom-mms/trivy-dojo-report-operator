FROM python:3.12@sha256:f964ddcb8416013f62f4b7a8c72a332ba4ccd284e39c263ea7bc0375ca8f2c4b as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:ee9a59cfdad294560241c9a8c8e40034f165feb4af7088c1479c2cdd84aafbed

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
