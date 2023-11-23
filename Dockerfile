FROM python:3.11-slim@sha256:1bc6a3e9356d64ea632791653bc71a56340e8741dab66434ab2739ebf6aed29d

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /

RUN poetry install --no-dev --no-cache

COPY src/* /src/

CMD ["poetry", "run", "kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/src/handlers.py", "--all-namespaces"]
