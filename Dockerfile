FROM python:3.12@sha256:f800043e7de77ae037f8012d71a99e5c59eb6b4945ef8f528e1ab79b04e26afd AS build

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.1.1

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-ansi

FROM python:3.12-slim@sha256:87b49ee9d18db77b0afc7e3adbd994acb9544695217f6e8b4ff352a076a9e6a6

RUN groupadd --gid 1000 app && \
    useradd --gid 1000 --uid 1000 app

COPY --from=build /app /app

COPY src/* /app/

RUN chown -R app:app /app

USER app

WORKDIR /app

ENTRYPOINT ["/app/.venv/bin/kopf"]

CMD ["run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--namespace=*"]