#!/usr/bin/env python3
"""
Debug script to check JWT keys used by Auth Service and Super ID Service.
This helps identify mismatch between signing and verification keys.
"""
import asyncio
import httpx
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Service URLs
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001")
SUPER_ID_SERVICE_URL = os.environ.get("SUPER_ID_SERVICE_URL", "http://localhost:8002")

# Client credentials - OAuth 2.0 client credentials flow
CLIENT_ID_STRING = os.environ.get("CLIENT_ID", "data_capture_rightmove_service") 
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "dev_client_secret")

# Convert client_id string to UUID (must match the same UUID algorithm used in create_oauth_client.py)
CLIENT_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, CLIENT_ID_STRING))

async def get_auth_token() -> Tuple[bool, Optional[str], Optional[str]]:
    """Get an authentication token from the Auth Service using client credentials"""
    print("🔑 Step 1: Getting authentication token from Auth Service...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get a token from the auth service
            token_url = f"{AUTH_SERVICE_URL}/api/v1/auth/token"
            print(f"Requesting auth token from: {token_url}")
            payload = {
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            }
            print(f"Using client_id: {CLIENT_ID}")
            print(f"Using client_secret: {CLIENT_SECRET}")
            
            response = await client.post(token_url, json=payload)
            
            if response.status_code == 200:
                token_data = response.json()
                token = token_data.get("access_token")
                if token:
                    print(f"✅ Successfully obtained auth token")
                    return True, token, None
                else:
                    print(f"❌ Token not found in response")
                    return False, None, "Token not found in response"
            else:
                print(f"❌ Failed to get auth token: {response.status_code}")
                print(f"Response: {response.text}")
                return False, None, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        print(f"Error getting auth token: {e}")
        return False, None, str(e)

async def decode_auth_token(token: str) -> None:
    """
    Print token details to help debug issues
    """
    import base64
    import json
    
    # Split the token into parts
    parts = token.split('.')
    if len(parts) != 3:
        print("❌ Invalid JWT token format")
        return
    
    # Decode the header and payload
    padding_needed = lambda s: (4 - len(s) % 4) % 4
    
    def decode_part(part):
        # Add padding if needed
        padded = part + ('=' * padding_needed(part))
        # Convert to standard base64 (replace -_ with +/)
        standardized = padded.replace('-', '+').replace('_', '/')
        # Decode
        return json.loads(base64.b64decode(standardized))
    
    try:
        header = decode_part(parts[0])
        payload = decode_part(parts[1])
        
        print("\n🔍 JWT Token Details:")
        print(f"Header: {json.dumps(header, indent=2)}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Check for critical fields
        print("\n🔑 Critical Fields:")
        print(f"Algorithm (alg): {header.get('alg')}")
        print(f"Issuer (iss): {payload.get('iss')}")
        print(f"Audience (aud): {payload.get('aud')}")
        print(f"Subject (sub): {payload.get('sub')}")
        
        # Check token expiration
        if 'exp' in payload:
            exp_timestamp = payload['exp']
            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            now = datetime.now()
            print(f"Expiration (exp): {exp_datetime} ({'expired' if now > exp_datetime else 'valid'})")
        
        # Check custom claims
        print("\n🏷️ Custom Claims:")
        for key, value in payload.items():
            if key not in ['iss', 'sub', 'aud', 'exp', 'iat', 'nbf', 'jti']:
                print(f"{key}: {value}")
                
    except Exception as e:
        print(f"❌ Error decoding token: {e}")

async def get_super_id(token: str) -> Tuple[bool, str, Optional[str]]:
    """Get Super ID from Super ID Service using auth token"""
    print("\n🆔 Step 2: Getting Super ID from Super ID Service...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get a super_id from the super_id service
            headers = {"Authorization": f"Bearer {token}"}
            super_id_url = f"{SUPER_ID_SERVICE_URL}/api/v1/super_ids"
            print(f"Requesting super ID from: {super_id_url}")
            print(f"Using token: {token[:20]}...{token[-10:]}")
            
            response = await client.post(
                super_id_url,
                headers=headers,
                json={"count": 1}  # Request a single Super ID
            )
            
            if response.status_code == 201:  # PRD specifies 201 Created response
                data = response.json()
                super_id = data.get("super_id")
                if not super_id:
                    print("❌ Super ID not found in response")
                    return False, "", "Super ID not found in response"
                print(f"✅ Successfully obtained Super ID: {super_id}")
                return True, super_id, None
            else:
                print(f"❌ Failed to get Super ID: {response.status_code}")
                print(f"Response: {response.text}")
                return False, "", f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        print(f"❌ Exception when getting Super ID: {str(e)}")
        return False, "", str(e)

async def check_auth_service_config():
    """Check Auth Service configuration"""
    print("\n🔧 Checking Auth Service configuration...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{AUTH_SERVICE_URL}/api/v1/health/config")
            if response.status_code == 200:
                config = response.json()
                print(f"✅ Auth Service config: {config}")
                # Look for JWT-related configs
                jwt_configs = {}
                for key, value in config.items():
                    if "jwt" in key.lower() or "secret" in key.lower():
                        jwt_configs[key] = "[REDACTED]" if "secret" in key.lower() else value
                print(f"🔑 JWT-related configs: {jwt_configs}")
                return True
            else:
                print(f"❌ Failed to get Auth Service config: {response.status_code}")
                print(f"Response: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Error checking Auth Service config: {e}")
        return False

async def check_super_id_service_config():
    """Check Super ID Service configuration"""
    print("\n🔧 Checking Super ID Service configuration...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{SUPER_ID_SERVICE_URL}/api/v1/health/config")
            if response.status_code == 200:
                config = response.json()
                print(f"✅ Super ID Service config: {config}")
                # Look for JWT-related configs
                jwt_configs = {}
                for key, value in config.items():
                    if "jwt" in key.lower() or "secret" in key.lower():
                        jwt_configs[key] = "[REDACTED]" if "secret" in key.lower() else value
                print(f"🔑 JWT-related configs: {jwt_configs}")
                return True
            else:
                print(f"❌ Failed to get Super ID Service config: {response.status_code}")
                print(f"Response: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Error checking Super ID Service config: {e}")
        return False

async def main():
    """Main function to run the debug process"""
    print("==================================================")
    print("JWT KEY DEBUG TOOL")
    print("==================================================")
    
    # Check Auth Service config
    await check_auth_service_config()
    
    # Check Super ID Service config
    await check_super_id_service_config()
    
    # Get auth token
    success, token, error = await get_auth_token()
    if not success:
        print(f"❌ Could not get auth token: {error}")
        return
        
    # Decode and analyze the token
    await decode_auth_token(token)
    
    # Try to get Super ID
    success, super_id, error = await get_super_id(token)
    if not success:
        print(f"❌ Could not get Super ID: {error}")
    
    print("\n==================================================")
    print("JWT DEBUG COMPLETE")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
