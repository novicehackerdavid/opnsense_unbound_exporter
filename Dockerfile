FROM python:3.11-slim

RUN pip install prometheus_client requests

WORKDIR /app
COPY unbound_export.py /app/unbound_export.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "unbound_export.py"]