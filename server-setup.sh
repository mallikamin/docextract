#!/bin/bash
# Server Setup Script for DocExtract
# Run this on your server: ssh user@154.192.134.4 'bash -s' < server-setup.sh

set -e

echo "==== DocExtract Server Setup ===="
echo "Server: 154.192.134.4"
echo "Domain: docextract-demo.duckdns.org"
echo ""

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to log out and back in."
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Create deployment directory
echo "Creating deployment directory..."
sudo mkdir -p /opt/docextract
sudo chown $USER:$USER /opt/docextract
cd /opt/docextract

# Create docker-compose.yml
echo "Creating docker-compose.yml..."
cat > docker-compose.yml << 'COMPOSE_EOF'
version: "3.8"

services:
  docextract:
    image: ghcr.io/GITHUB_USERNAME/docextract:latest
    container_name: docextract
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MAX_FILE_SIZE_MB=50
      - OCR_DPI=300
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: docextract-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - docextract

  duckdns:
    image: linuxserver/duckdns
    container_name: duckdns
    restart: unless-stopped
    environment:
      - TZ=UTC
      - SUBDOMAINS=docextract-demo
      - TOKEN=${DUCKDNS_TOKEN}
      - LOG_FILE=false
COMPOSE_EOF

# Create nginx config
echo "Creating nginx config..."
cat > nginx.conf << 'NGINX_EOF'
events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    proxy_buffering off;
    proxy_cache off;

    upstream docextract {
        server docextract:8000;
    }

    server {
        listen 80;
        server_name _;

        client_max_body_size 100M;

        location / {
            proxy_pass http://docextract;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_http_version 1.1;
            proxy_set_header Connection '';
            proxy_read_timeout 600s;
        }

        location /api/jobs/ {
            proxy_pass http://docextract;
            proxy_set_header Host $host;
            proxy_buffering off;
            proxy_cache off;
            proxy_http_version 1.1;
            proxy_set_header Connection '';
        }
    }
}
NGINX_EOF

# Create .env template
echo "Creating .env template..."
cat > .env.example << 'ENV_EOF'
ANTHROPIC_API_KEY=sk-ant-...
DUCKDNS_TOKEN=your-token-here
ENV_EOF

echo ""
echo "==== Setup Complete ===="
echo ""
echo "Next steps:"
echo "1. Create .env file with your keys:"
echo "   cd /opt/docextract"
echo "   nano .env"
echo ""
echo "2. Add:"
echo "   ANTHROPIC_API_KEY=sk-ant-api03-..."
echo "   DUCKDNS_TOKEN=your-duckdns-token"
echo ""
echo "3. Pull and start:"
echo "   docker-compose pull"
echo "   docker-compose up -d"
echo ""
echo "4. Check status:"
echo "   docker-compose ps"
echo "   curl http://localhost/health"
echo ""
