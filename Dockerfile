FROM python:3.12@sha256:3c085580c5f27bb93b90ecf6be3fb62a093d40d7552d13b9cfbfb0f117064ae6 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.12-slim@sha256:6fdb82b3104290018049ba21e2d41160dffec5b1f3e0d4c96f7ee74eaca1624b

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]