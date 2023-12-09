FROM python:3.12@sha256:6d7fa2d5653e1d0eb464a672ded01f973e49e4a7ded59703c7bdcf6b92eac736 as build

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.in-project true
RUN poetry install --no-ansi

FROM python:3.12-slim@sha256:19a6235339a74eca01227b03629f63b6f5020abc21142436eced6ec3a9839a76

COPY --from=build /app /app

COPY src/* /app/

CMD ["/app/.venv/bin/kopf", "run", "--liveness=http://0.0.0.0:8080/healthz", "/app/handlers.py", "--all-namespaces"]
