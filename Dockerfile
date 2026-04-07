FROM python:3.12@sha256:c5a24d6f55608f2c41a30908c1e8ffe6e8e67c149bcb535daedf1646eace6efd AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.12-slim@sha256:5072b08ad74609c5329ab4085a96dfa873de565fb4751a4cfcd7dcc427661df0

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

RUN apt-get update -y -qq && \
    apt-get install -y -qq --no-install-recommends jq=1.7.1-6+deb13u1 kubectl=1.32.3+ds-2 curl=8.14.1-2+deb13u2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

ENTRYPOINT ["/app/.venv/bin/kopf"]

CMD ["run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--namespace=*"]