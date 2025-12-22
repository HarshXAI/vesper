"""
E2E Tests Package
==================

Smoke and integration tests for deployment validation.
"""

import os

# Test configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
AIRFLOW_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
TIMEOUT_SECONDS = int(os.getenv("TEST_TIMEOUT", "30"))
