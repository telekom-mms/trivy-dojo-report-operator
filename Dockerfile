FROM python:3.11-slim

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /

RUN poetry install --no-dev --no-cache

COPY src/* /src/

CMD ["poetry", "run", "kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/src/handlers.py", "--all-namespaces"]
