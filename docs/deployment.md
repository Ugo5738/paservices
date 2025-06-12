# Deployment Guide for Authentication Service

## HTTPS Requirements

### Production Deployment

For security reasons, this authentication service **MUST** be deployed behind a reverse proxy that handles TLS termination and enforces HTTPS. This is critical for protecting sensitive information such as authentication tokens and user credentials.

#### Recommended Reverse Proxy Options

- **Nginx**: Popular, high-performance HTTP server and reverse proxy
- **Traefik**: Modern HTTP reverse proxy and load balancer made to deploy microservices
- **HAProxy**: Reliable, high-performance TCP/HTTP load balancer
- **Caddy**: Modern web server with automatic HTTPS

#### Minimum TLS Requirements

- TLS version 1.2 or higher
- Strong cipher suites (disable weak ciphers)
- Forward Secrecy support
- HTTP Strict Transport Security (HSTS) headers

#### Sample Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name auth.yourdomain.com;

    # SSL/TLS certificates
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    # TLS settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # HSTS (15768000 seconds = 6 months)
    add_header Strict-Transport-Security "max-age=15768000; includeSubDomains; preload";

    # Other security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://localhost:8000; # Assuming the auth service runs on port 8000
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name auth.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

### Local Development HTTPS Testing

For local development and testing with HTTPS, you can use Uvicorn's built-in SSL support:

```bash
uvicorn auth_service.main:app --ssl-keyfile=./local-cert.key --ssl-certfile=./local-cert.pem --reload
```

To generate self-signed certificates for local development:

```bash
openssl req -x509 -newkey rsa:4096 -nodes -out local-cert.pem -keyout local-cert.key -days 365
```

> **Note**: Self-signed certificates will trigger browser warnings. This is expected in development environments but not acceptable for production.

## Environment Variables

Ensure the following environment variables are properly set for production deployments:

```
ENVIRONMENT=production
BASE_URL=https://auth.yourdomain.com  # Must use HTTPS
```

## Security Considerations

- Regularly update SSL/TLS certificates before expiration
- Configure proper logging for security events
- Use strong password policies
- Enable rate limiting on all authentication endpoints
- Implement proper CORS policies based on your application domains
