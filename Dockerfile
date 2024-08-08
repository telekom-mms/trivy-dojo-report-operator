FROM python:3.12@sha256:c7862834f921957523cc4dab6d7795a7a0d19f1cd156c1ecd3a3a08c1108c9a4 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.12-slim@sha256:105e9d85a67db1602e70fa2bbb49c1e66bae7e3bdcb6259344fe8ca116434f74

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]