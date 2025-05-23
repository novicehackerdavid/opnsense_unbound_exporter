import os
import time
import logging
import requests
from prometheus_client import start_http_server, Gauge
from flask import Flask, Response

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment configuration
OPNSENSE_HOST = os.getenv("OPNSENSE_HOST", "192.168.1.1")
OPNSENSE_PORT = os.getenv("OPNSENSE_PORT", "443")
EXPORTER_PORT = int(os.getenv("EXPORT_PORT", "9798"))
API_KEY = os.getenv("OPNSENSE_API_KEY")
API_SECRET = os.getenv("OPNSENSE_API_SECRET")
INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "30"))

# Endpoint
UNBOUND_URL = f"https://{OPNSENSE_HOST}:{OPNSENSE_PORT}/api/unbound/overview/totals/100"

# Disable insecure request warnings
requests.packages.urllib3.disable_warnings()

# Prometheus metrics
metrics = {
    'total': Gauge('unbound_queries_total', 'Total number of Unbound queries'),
    'passed': Gauge('unbound_queries_passed_total', 'Total queries that were passed'),
    'blocklist_size': Gauge('unbound_blocklist_size', 'Size of the blocklist'),
    'resolved': Gauge('unbound_queries_resolved_total', 'Total resolved queries'),
    'blocked': Gauge('unbound_queries_blocked_total', 'Total blocked queries'),
    'local': Gauge('unbound_queries_local_total', 'Total local queries'),
}

top_domains_metric = Gauge('unbound_top_domain_queries_total', 'Top queried domains', ['domain'])
top_blocked_metric = Gauge('unbound_top_blocked_domain_queries_total', 'Top blocked domains', ['domain', 'blocklist'])

# Auth headers if needed (currently unused)
HEADERS = {
    "User-Agent": "unbound_export/1.0",
}

def fetch_unbound_data():
    try:
        response = requests.get(UNBOUND_URL, headers=HEADERS, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch data from Unbound API: {e}")
        return None

def update_metrics(data):
    try:
        metrics['total'].set(data.get("total", 0))
        metrics['passed'].set(data.get("passed", 0))
        metrics['blocklist_size'].set(data.get("blocklist_size", 0))
        metrics['resolved'].set(data.get("resolved", {}).get("total", 0))
        metrics['blocked'].set(data.get("blocked", {}).get("total", 0))
        metrics['local'].set(data.get("local", {}).get("total", 0))

        top_domains_metric.clear()
        for domain, stats in data.get("top", {}).items():
            top_domains_metric.labels(domain=domain).set(stats.get("total", 0))

        top_blocked_metric.clear()
        for domain, stats in data.get("top_blocked", {}).items():
            top_blocked_metric.labels(
                domain=domain,
                blocklist=stats.get("blocklist", "unknown")
            ).set(stats.get("total", 0))

        logging.info("Metrics updated successfully.")
    except Exception as e:
        logging.error(f"Error updating metrics: {e}")

# Flask app to serve /metrics endpoint
app = Flask(__name__)

@app.route("/metrics")
def metrics_endpoint():
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

def run_exporter():
    logging.info(f"Starting unbound_export using OPNSENSE_HOST={OPNSENSE_HOST} on PORT={EXPORT_PORT}")
    start_http_server(EXPORT_PORT)
    while True:
        data = fetch_unbound_data()
        if data:
            update_metrics(data)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    from threading import Thread
    Thread(target=run_exporter).start()
    app.run(host="0.0.0.0", port=EXPORT_PORT)
