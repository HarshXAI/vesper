/**
 * KA-CHOW Auto-Patch
 * Issue: Hardcoded API keys found in configuration files.
 * Service: vesper-api-gateway
 *
 * The code was modified to replace the hardcoded API key with a dynamic retrieval using os.getenv('API_KEY'). This change enhances security by ensuring that sensitive information like API keys are not stored directly in the codebase, reducing the risk of accidental exposure. By using environment variables, the API key can be managed securely outside the codebase.
 */

import os

class VesperApiGateway:
    def __init__(self):
        self.api_key = os.getenv('API_KEY')

    def get_api_key(self):
        return self.api_key