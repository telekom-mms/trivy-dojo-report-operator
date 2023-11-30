FROM python:3.11-slim@sha256:23f52205321f806c2cc742cefbf837e0d25101388c043e860c7817985230565c

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /

RUN poetry install --no-dev --no-cache

COPY src/* /src/

CMD ["poetry", "run", "kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/src/handlers.py", "--all-namespaces"]
