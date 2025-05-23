FROM python:3.11-slim

WORKDIR /app

# Use a requirements.txt file for clarity and caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python script
COPY unbound_export.py .

# Prevent buffering logs in Docker
ENV PYTHONUNBUFFERED=1

CMD ["python", "unbound_export.py"]