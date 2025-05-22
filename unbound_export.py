import os
import time
import requests
from prometheus_client import start_http_server, Gauge

# Load environment variables
API_KEY = os.getenv("OPNSENSE_API_KEY")
API_SECRET = os.getenv("OPNSENSE_API_SECRET")
OPNSENSE_HOST = os.getenv("OPNSENSE_HOST", "https://192.168.1.1")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9798"))

# Prometheus metrics
total_queries = Gauge('unbound_total_queries', 'Total DNS queries')
blocked_queries = Gauge('unbound_blocked_queries', 'Blocked DNS queries')
passed_queries = Gauge('unbound_passed_queries', 'Passed DNS queries')
blocklist_size = Gauge('unbound_blocklist_size', 'Size of blocklist')
top_blocked = Gauge('unbound_top_blocked_domains', 'Top blocked domains', ['domain'])
top_allowed = Gauge('unbound_top_allowed_domains', 'Top allowed domains', ['domain'])

# Headers for API auth
headers = {
    "Authorization": f"Basic {API_KEY}:{API_SECRET}"
}

def fetch_totals():
    url = f"{OPNSENSE_HOST}/api/unbound/overview/totals/100"
    response = requests.get(url, verify=False, auth=(API_KEY, API_SECRET))
    response.raise_for_status()
    return response.json()

def update_metrics():
    data = fetch_totals()

    total = data.get("total_num_queries", 0)
    blocked = data.get("num_blocked", 0)
    passed = total - blocked

    total_queries.set(total)
    blocked_queries.set(blocked)
    passed_queries.set(passed)

    blocklist_size.set(len(data.get("blocklisted_domains", [])))

    for domain, info in data.get("top_blocked", {}).items():
        top_blocked.labels(domain=domain).set(info.get("count", 0))

    for domain, info in data.get("top_allowed", {}).items():
        top_allowed.labels(domain=domain).set(info.get("count", 0))

if __name__ == "__main__":
    start_http_server(EXPORTER_PORT)
    while True:
        try:
            update_metrics()
        except Exception as e:
            print(f"Error updating metrics: {e}")
        time.sleep(60)