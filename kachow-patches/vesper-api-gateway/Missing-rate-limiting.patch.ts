/**
 * KA-CHOW Auto-Patch
 * Issue: Missing rate limiting
 * Service: vesper-api-gateway
 *
 * The code introduces a rate limiting decorator that tracks the number of requests from each client IP within a 60-second window. It maintains a dictionary to store timestamps of requests for each IP. When a request is made, it filters out timestamps older than 60 seconds and checks if the number of requests exceeds the limit of 100. If it does, it returns a 429 error. Otherwise, it appends the current timestamp and processes the request. This change prevents abuse by limiting excessive requests while preserving existing functionality.
 */

from flask import Flask, request, jsonify
from functools import wraps
from time import time

app = Flask(__name__)

RATE_LIMIT = 100
TIME_WINDOW = 60
client_requests = {}


def rate_limit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = time()
        if client_ip not in client_requests:
            client_requests[client_ip] = []
        # Filter out requests that are outside the time window
        client_requests[client_ip] = [timestamp for timestamp in client_requests[client_ip] if current_time - timestamp < TIME_WINDOW]
        if len(client_requests[client_ip]) >= RATE_LIMIT:
            return jsonify({'error': 'Too many requests'}), 429
        client_requests[client_ip].append(current_time)
        return func(*args, **kwargs)
    return wrapper

@app.route('/public-endpoint')
@rate_limit
def public_endpoint():
    return jsonify({'message': 'This is a public endpoint'})

if __name__ == '__main__':
    app.run()