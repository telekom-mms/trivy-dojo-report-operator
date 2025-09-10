FROM python:3.13@sha256:35c05b6d32b11a1a8134f35dd0db68ef6fbb21ce62934a7aec6d50977915a92c AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.13-slim@sha256:1bca0202e953784ac2a1daf36ebbc9cbebed48afcfba12d1225aaab3793eca33

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]