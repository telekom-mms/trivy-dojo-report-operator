FROM python:3.12@sha256:9465269ac36c61995cbbc722d1223b26cfa0ce9912bd1cd93fae0b161fcbb8c0 AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.12-slim@sha256:a75662dfec8d90bd7161c91050be2e0a9b21d284f3b7a7253d5db25f7d583fb3

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

ENTRYPOINT ["/app/.venv/bin/kopf"]

CMD ["run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--namespace=*"]