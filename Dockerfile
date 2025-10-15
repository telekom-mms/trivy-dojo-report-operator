FROM python:3.14@sha256:e3a6ccbe44d9cbfa4f107f238a0e95fa70e0d084e87689222e951d062ac89854 AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.14-slim@sha256:5cfac249393fa6c7ebacaf0027a1e127026745e603908b226baa784c52b9d99b

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]