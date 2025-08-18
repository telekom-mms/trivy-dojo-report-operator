FROM python:3.13@sha256:3b2f1b9c9948e9dc96e1a2f4668ba9870ff43ab834f91155697476142b3bc299 AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.13-slim@sha256:27f90d79cc85e9b7b2560063ef44fa0e9eaae7a7c3f5a9f74563065c5477cc24

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]