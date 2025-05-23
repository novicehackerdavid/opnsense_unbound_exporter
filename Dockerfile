# Use a minimal Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install required packages
RUN pip install --no-cache-dir flask prometheus_client requests

# Set working directory
WORKDIR /app

# Copy your exporter script into the container
COPY unbound_export.py .

# Expose the exporter port
EXPOSE 9798

# Command to run the exporter
CMD ["python", "unbound_export.py"]