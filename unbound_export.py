import os
import time
import logging
import requests
from requests.auth import HTTPBasicAuth
from prometheus_client import start_http_server, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Flask, Response
import urllib3

# Disable SSL warnings if using self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Debugging flag
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# Logging setup
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

# Environment configuration
OPNSENSE_HOST = os.getenv("OPNSENSE_HOST", "192.168.1.1")
OPNSENSE_PORT = os.getenv("OPNSENSE_PORT", "443")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9797"))
FLASK_PORT = int(os.getenv("FLASK_PORT", "9798"))
API_KEY = os.getenv("OPNSENSE_API_KEY")
API_SECRET = os.getenv("OPNSENSE_API_SECRET")
INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "30"))

# Check for required environment variables
if not API_KEY or not API_SECRET:
    logging.error("OPNSENSE_API_KEY and OPNSENSE_API_SECRET must be set!")
    exit(1)

# Prometheus metrics
metrics = {
    'total': Gauge('unbound_queries_total', 'Total number of Unbound queries'),
    'passed': Gauge('unbound_queries_passed_total', 'Total queries that were passed'),
    'blocklist_size': Gauge('unbound_blocklist_size', 'Size of the blocklist'),
    'resolved': Gauge('unbound_queries_resolved_total', 'Total resolved queries'),
    'resolved_percent': Gauge('unbound_queries_resolved_percent', 'Percentage of resolved queries'),
    'blocked': Gauge('unbound_queries_blocked_total', 'Total blocked queries'),
    'blocked_percent': Gauge('unbound_queries_blocked_percent', 'Percentage of blocked queries'),
    'local': Gauge('unbound_queries_local_total', 'Total local queries'),
    'local_percent': Gauge('unbound_queries_local_percent', 'Percentage of local queries'),
}

top_domains_metric = Gauge('unbound_top_domain_queries_total', 'Top queried domains', ['domain'])
top_domains_percent_metric = Gauge('unbound_top_domain_queries_percent', 'Top queried domains percentage', ['domain'])
top_blocked_metric = Gauge('unbound_top_blocked_domain_queries_total', 'Top blocked domains', ['domain', 'blocklist'])
top_blocked_percent_metric = Gauge('unbound_top_blocked_domain_queries_percent', 'Top blocked domains percentage', ['domain', 'blocklist'])

def fetch_unbound_data():
    """Fetch data from OPNsense Unbound API using Basic Authentication"""
    try:
        # Use the correct endpoint path
        path = "/api/unbound/overview/totals/100"
        url = f"https://{OPNSENSE_HOST}:{OPNSENSE_PORT}{path}"
        
        # Use HTTPBasicAuth with API key as username and API secret as password
        auth = HTTPBasicAuth(API_KEY, API_SECRET)
        
        if DEBUG_MODE:
            logging.debug(f"[DEBUG] Requesting URL: {url}")
            logging.debug(f"[DEBUG] Using API Key: {API_KEY[:8]}...")  # Show only first 8 chars
        
        # Make the request with basic auth
        response = requests.get(
            url,
            auth=auth,
            verify=False,  # Set to True if you have valid SSL certificates
            timeout=10
        )
        
        if DEBUG_MODE:
            logging.debug(f"[DEBUG] Status code: {response.status_code}")
            logging.debug(f"[DEBUG] Response headers: {dict(response.headers)}")
            if response.status_code != 200:
                logging.debug(f"[DEBUG] Response text: {response.text}")
        
        response.raise_for_status()
        data = response.json()
        
        logging.info(f"Successfully fetched Unbound data: {data.get('total', 0)} total queries")
        return data
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logging.error("Authentication failed! Check your API key and secret.")
            logging.error("Make sure OPNSENSE_API_KEY and OPNSENSE_API_SECRET are correctly set.")
        else:
            logging.error(f"HTTP error occurred: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected error fetching data: {e}")
    
    return None

def update_metrics(data):
    """Update Prometheus metrics with the fetched data"""
    try:
        # Basic metrics
        metrics['total'].set(data.get("total", 0))
        metrics['passed'].set(data.get("passed", 0))
        metrics['blocklist_size'].set(data.get("blocklist_size", 0))
        
        # Resolved metrics
        resolved_data = data.get("resolved", {})
        metrics['resolved'].set(resolved_data.get("total", 0))
        metrics['resolved_percent'].set(float(resolved_data.get("pcnt", 0)))
        
        # Blocked metrics
        blocked_data = data.get("blocked", {})
        metrics['blocked'].set(blocked_data.get("total", 0))
        metrics['blocked_percent'].set(float(blocked_data.get("pcnt", 0)))
        
        # Local metrics
        local_data = data.get("local", {})
        metrics['local'].set(local_data.get("total", 0))
        metrics['local_percent'].set(float(local_data.get("pcnt", 0)))
        
        # Clear and update top domains
        top_domains_metric.clear()
        top_domains_percent_metric.clear()
        for domain, stats in data.get("top", {}).items():
            top_domains_metric.labels(domain=domain).set(stats.get("total", 0))
            top_domains_percent_metric.labels(domain=domain).set(float(stats.get("pcnt", 0)))
        
        # Clear and update top blocked domains
        top_blocked_metric.clear()
        top_blocked_percent_metric.clear()
        for domain, stats in data.get("top_blocked", {}).items():
            blocklist = stats.get("blocklist", "unknown")
            top_blocked_metric.labels(domain=domain, blocklist=blocklist).set(stats.get("total", 0))
            top_blocked_percent_metric.labels(domain=domain, blocklist=blocklist).set(float(stats.get("pcnt", 0)))
        
        logging.info("Metrics updated successfully.")
    except Exception as e:
        logging.error(f"Error updating metrics: {e}")

# Flask app to serve /metrics endpoint
app = Flask(__name__)

@app.route("/metrics")
def metrics_endpoint():
    """Serve Prometheus metrics"""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route("/health")
def health_check():
    """Health check endpoint"""
    return "OK", 200

def run_exporter():
    """Main exporter loop"""
    logging.info(f"Starting Unbound exporter for {OPNSENSE_HOST}:{OPNSENSE_PORT}")
    logging.info(f"Prometheus metrics available on port {EXPORTER_PORT}")
    logging.info(f"Flask metrics endpoint available on port {FLASK_PORT}")
    
    # Start Prometheus HTTP server
    start_http_server(EXPORTER_PORT)
    
    # Initial data fetch
    data = fetch_unbound_data()
    if data:
        update_metrics(data)
    
    # Main loop
    while True:
        time.sleep(INTERVAL)
        data = fetch_unbound_data()
        if data:
            update_metrics(data)

if __name__ == "__main__":
    from threading import Thread
    
    # Start the exporter in a separate thread
    exporter_thread = Thread(target=run_exporter, daemon=True)
    exporter_thread.start()
    
    # Run Flask app in the main thread
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)