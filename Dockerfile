FROM python:3.13@sha256:cea505b81701dd9e46b8dde96eaa8054c4bd2035dbb660edeb7af947ed38a0ad as build

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.13-slim@sha256:1127090f9fff0b8e7c3a1367855ef8a3299472d2c9ed122948a576c39addeaf1

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]