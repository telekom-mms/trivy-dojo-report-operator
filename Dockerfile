FROM python:3.12@sha256:336461f63f4eb1100e178d5acbfea3d1a5b2a53dea88aa0f9b8482d4d02e981c as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:36d57d7f9948fefe7b6092cfe8567da368033e71ba281b11bb9eeffce3d45bc6

RUN groupadd --gid 1000 app && \
    useradd --create-home --gid 1000 --uid 1000 app

WORKDIR /home/app

COPY --from=build /app /app

COPY src/* /app/

USER app

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
