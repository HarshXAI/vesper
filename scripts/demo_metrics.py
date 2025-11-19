#!/usr/bin/env python3
"""Demo Prometheus metrics exporter.

Run this locally to expose sample metrics on port 9101 so Prometheus can scrape
and Grafana can visualize them. Intended for local development only.
"""
import time
import random
from prometheus_client import start_http_server, Gauge, Counter, Histogram


GAUGE_NAME = 'demo_temperature_celsius'
COUNTER_NAME = 'demo_requests_total'
HISTOGRAM_NAME = 'demo_response_time_seconds'


def main(port: int = 9101):
    # Create metrics
    temp_gauge = Gauge(GAUGE_NAME, 'Synthetic temperature in Celsius')
    req_counter = Counter(COUNTER_NAME, 'Synthetic number of requests')
    resp_hist = Histogram(HISTOGRAM_NAME, 'Synthetic response time seconds')

    # Start HTTP server for Prometheus to scrape
    start_http_server(port)
    print(f"Demo metrics server running on :{port} (metrics endpoint /)")

    # Loop and emit synthetic values
    try:
        while True:
            # Update gauge with a slowly varying sine-like value + noise
            temp = 20.0 + 5.0 * random.uniform(-1, 1) + 0.5 * random.random()
            temp_gauge.set(round(temp, 3))

            # Increment counter by 1-5
            inc = random.randint(1, 5)
            req_counter.inc(inc)

            # Observe random response times
            for _ in range(random.randint(1, 3)):
                resp_time = max(0.01, random.random() * 0.8)
                resp_hist.observe(resp_time)

            # Sleep before next update
            time.sleep(2)

    except KeyboardInterrupt:
        print("Stopping demo metrics server")


if __name__ == '__main__':
    main()
