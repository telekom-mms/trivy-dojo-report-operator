FROM python:3.13@sha256:08471c63c5fdf2644adc142a7fa8d0290eb405cda14c473fbe5b4cd0933af601 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.13-slim@sha256:ae9f9ac89467077ed1efefb6d9042132d28134ba201b2820227d46c9effd3174

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]