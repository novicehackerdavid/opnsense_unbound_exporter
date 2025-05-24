FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install required packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy your exporter script into the container
COPY unbound_export.py .

# Expose both the Prometheus metrics port and Flask port
EXPOSE 9797 9798

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:9798/health || exit 1

# Command to run the exporter
CMD ["python", "unbound_export.py"]