FROM python:3.11-slim

COPY requirements.txt /
RUN pip install -r /requirements.txt

COPY src/* /src/

CMD kopf run /src/handlers.py --verbose
