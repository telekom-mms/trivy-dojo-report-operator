FROM python:3.11-slim@sha256:f89d4d260b6a5caa6aa8e0e14b162deb76862890c91779c31f762b22e72a6cef

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /

RUN poetry install --no-dev --no-cache

COPY src/* /src/

CMD ["poetry", "run", "kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/src/handlers.py", "--all-namespaces"]
