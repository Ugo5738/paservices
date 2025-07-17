# scripts/test_production_flow.py

import asyncio

import httpx

# --- Configuration ---
# CHANGE THESE URLs to your public domains
AUTH_SERVICE_URL = "https://auth.supersami.com"
SUPER_ID_SERVICE_URL = "https://superid.supersami.com"
DATA_CAPTURE_SERVICE_URL = "https://data-capture-rightmove.supersami.com"

# Use the real M2M client credentials from your GitHub secrets
# It's okay to have them in a local script that you don't commit
CLIENT_ID = "fe2c7655-0860-4d98-9034-cd5e1ac90a41"
CLIENT_SECRET = "dev-rightmove-service-secret"

# ... (the rest of the script remains the same) ...

# The rest of your test script for getting a token,
# getting a super_id, and capturing data should work perfectly.
