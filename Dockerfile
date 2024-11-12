FROM python:3.12@sha256:f2268d7eaa0ffed6f078159432baa81db9be1a6748bec566153e1c20a46a2715 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.12-slim@sha256:ccf9f245a6ad1d215cb0124a669ec50d00a7841c4eecf428b6220e06835ca06c

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]