#!/usr/bin/env python3

import os
import base64

# Generate a consistent secret key string that we can use in both services
secret_key = base64.b64encode(b'super_id_and_auth_service_shared_secret_key').decode('utf-8')
print(f"Generated shared secret key: {secret_key}")

print("\nAdd these lines to both .env.dev files:")
print(f"AUTH_SERVICE_M2M_JWT_SECRET_KEY={secret_key}")
print(f"SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY={secret_key}")

print("\nTo apply immediately to running containers, run:")
print(f"docker-compose exec auth_service sh -c 'echo \"AUTH_SERVICE_M2M_JWT_SECRET_KEY={secret_key}\" > /tmp/env.txt && export AUTH_SERVICE_M2M_JWT_SECRET_KEY={secret_key}'")
print(f"docker-compose exec super_id_service sh -c 'echo \"SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY={secret_key}\" > /tmp/env.txt && export SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY={secret_key}'")

print("\nThen restart the services:")
print("docker-compose restart auth_service super_id_service")
