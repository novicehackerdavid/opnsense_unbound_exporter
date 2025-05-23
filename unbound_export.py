import requests
from prometheus_client import start_http_server, Gauge
import time
import logging
import os

# Configure logging to file
logging.basicConfig(
    filename='/app/unbound_export.log',
    filemode='w',  # overwrite log on each run
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

OPNSENSE_HOST = os.getenv('OPNSENSE_HOST', '192.168.1.1')
API_URL = f"https://{OPNSENSE_HOST}/api/unbound/stats"

# Prometheus metrics
total_queries = Gauge('unbound_total_queries', 'Total number of DNS queries')
blocked_queries = Gauge('unbound_blocked_queries', 'Number of blocked DNS queries')
allowed_queries = Gauge('unbound_allowed_queries', 'Number of allowed DNS queries')
top_blocked_domains = Gauge('unbound_top_blocked_domains', 'Top blocked domains', ['domain'])
top_allowed_domains = Gauge('unbound_top_allowed_domains', 'Top allowed domains', ['domain'])
blocklist_size = Gauge('unbound_blocklist_size', 'Size of the DNS blocklist')

def fetch_unbound_stats():
    try:
        response = requests.get(API_URL, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch data from Unbound API: {e}")
        return {}

def update_metrics(data):
    try:
        total = data.get("total_queries", 0)
        blocked = data.get("blocked_queries", 0)
        allowed = data.get("allowed_queries", 0)
        top_blocked = data.get("top_blocked", {})
        top_allowed = data.get("top_allowed", {})
        bl_size = data.get("blocklist_size", 0)

        total_queries.set(total)
        blocked_queries.set(blocked)
        allowed_queries.set(allowed)
        blocklist_size.set(bl_size)

        # Clear previous domain labels to avoid label bloat
        for label in list(top_blocked_domains._metrics):
            top_blocked_domains.remove(*label)
        for label in list(top_allowed_domains._metrics):
            top_allowed_domains.remove(*label)

        for domain, count in top_blocked.items():
            top_blocked_domains.labels(domain=domain).set(count)
        for domain, count in top_allowed.items():
            top_allowed_domains.labels(domain=domain).set(count)

        logging.info("Metrics updated successfully.")
    except Exception as e:
        logging.error(f"Failed to update metrics: {e}")

def main():
    logging.info(f"Starting unbound_export using OPNSENSE_HOST={OPNSENSE_HOST}")
    start_http_server(8000)
    while True:
        data = fetch_unbound_stats()
        update_metrics(data)
        time.sleep(30)

if __name__ == "__main__":
    main()