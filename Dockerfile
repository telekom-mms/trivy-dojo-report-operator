FROM python:3.12-slim@sha256:eb6d3208444a54418be98f83f1006f6d78ef17144f1cd9eb4e5945d4851af355

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /

RUN poetry install --no-dev --no-cache

COPY src/* /src/

CMD ["poetry", "run", "kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/src/handlers.py", "--all-namespaces"]
