"""
Generate a test JWT (HS256) for local development.

Usage:
    python scripts/generate_test_token.py

Reads M2M_JWT_SECRET_KEY and M2M_JWT_AUDIENCE from the environment
(source .env.dev first) or uses defaults.
"""

import os
import time

import jwt

SECRET = os.getenv(
    "DATA_CAPTURE_SERVICE_M2M_JWT_SECRET_KEY",
    "oIAE7ZCEZtCmT7HazaDddU6IcWCKKOTS44LPyT7nFQM",
)
AUDIENCE = os.getenv("DATA_CAPTURE_SERVICE_M2M_JWT_AUDIENCE", "paservices_microservices")
ISSUER = os.getenv("DATA_CAPTURE_SERVICE_AUTH_SERVICE_ISSUER", "paservices_auth_service")

now = int(time.time())

payload = {
    "sub": "dev-test-client",
    "client_id": "dev-test-client",
    "service": "data_capture_service",
    "aud": AUDIENCE,
    "iss": ISSUER,
    "iat": now,
    "exp": now + 86400,  # 24 hours
    "scope": "data_capture:read data_capture:write",
}

token = jwt.encode(payload, SECRET, algorithm="HS256")
print(token)
