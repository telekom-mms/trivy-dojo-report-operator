FROM python:3.12@sha256:63828510c8b5ccce3bf0d6fabd6f3d17d4effa1ffe690f80a67c8e2d394e03ee AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

# hadolint ignore=DL3008
RUN apt-get update -y -qq && \
    apt-get install -y -qq --no-install-recommends jq kubectl curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

ENTRYPOINT ["/app/.venv/bin/kopf"]

CMD ["run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--namespace=*"]
