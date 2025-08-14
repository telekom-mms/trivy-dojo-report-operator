FROM python:3.13@sha256:50cbf8e58ca53a806b99250b1ba2d16c19433e8c42e7eb4ac4ea924b095e280b AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.13-slim@sha256:2a928e11761872b12003515ea59b3c40bb5340e2e5ecc1108e043f92be7e473d

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]