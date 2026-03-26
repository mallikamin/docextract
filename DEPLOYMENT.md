# DocExtract - Deployment Guide

## Quick Deploy Options

### Option 1: GitHub Actions + VPS (Recommended)

**Setup Steps:**

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/docextract.git
   git push -u origin main
   ```

2. **Set GitHub Secrets**
   Go to `Settings → Secrets → Actions` and add:
   - `DEPLOY_HOST`: Your server IP or domain
   - `DEPLOY_USER`: SSH username (e.g., `ubuntu`)
   - `DEPLOY_SSH_KEY`: Your private SSH key
   - `ANTHROPIC_API_KEY`: Your Claude API key

3. **Prepare Your Server**
   ```bash
   # SSH into your VPS
   ssh user@your-server.com

   # Install Docker
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER

   # Create deployment directory
   sudo mkdir -p /opt/docextract
   sudo chown $USER:$USER /opt/docextract
   cd /opt/docextract

   # Copy docker-compose.prod.yml
   wget https://raw.githubusercontent.com/YOUR_USERNAME/docextract/main/docker/docker-compose.prod.yml -O docker-compose.yml

   # Create .env file
   cat > .env << EOF
   ANTHROPIC_API_KEY=sk-ant-...
   GITHUB_REPOSITORY=YOUR_USERNAME/docextract
   DUCKDNS_SUBDOMAIN=your-subdomain
   DUCKDNS_TOKEN=your-duckdns-token
   EOF
   ```

4. **Push to GitHub → Auto-deploy**
   Every push to `main` triggers automatic deployment!

---

### Option 2: DuckDNS + Home/Office Server

**Get Free Domain:**
1. Go to [duckdns.org](https://www.duckdns.org)
2. Sign in (Google/Reddit/GitHub)
3. Create a subdomain: `docextract-demo.duckdns.org`
4. Copy your token

**Run on Local Server:**
```bash
# Clone repo
git clone https://github.com/YOUR_USERNAME/docextract.git
cd docextract

# Create .env
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-api03-...
DUCKDNS_SUBDOMAIN=docextract-demo
DUCKDNS_TOKEN=your-token-here
EOF

# Generate self-signed SSL cert (for HTTPS)
mkdir -p docker/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/nginx/ssl/key.pem \
  -out docker/nginx/ssl/cert.pem \
  -subj "/CN=docextract-demo.duckdns.org"

# Start all services
docker-compose -f docker/docker-compose.prod.yml up -d

# Check status
docker-compose -f docker/docker-compose.prod.yml ps
curl https://docextract-demo.duckdns.org/health
```

**Share with Client:**
Send them: `https://docextract-demo.duckdns.org`

---

### Option 3: Cloud Platforms (One-Click Deploy)

#### Render.com (Free Tier)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Click "Deploy to Render"
2. Connect your GitHub repo
3. Add environment variable: `ANTHROPIC_API_KEY`
4. Deploy → Get URL: `docextract.onrender.com`

#### Railway.app
```bash
railway login
railway init
railway add
railway up
railway open
```

#### DigitalOcean App Platform
1. Go to Apps → Create App
2. Connect GitHub repo
3. Select `docker/Dockerfile`
4. Add env vars
5. Deploy → Get URL

---

## Production Checklist

### Security
- [ ] HTTPS enabled (Let's Encrypt or self-signed)
- [ ] Firewall configured (allow 80, 443)
- [ ] API key in environment variables (not in code)
- [ ] Rate limiting configured in nginx
- [ ] File upload size limited (100MB max)

### Monitoring
- [ ] Health endpoint working: `/health`
- [ ] Logs accessible: `docker-compose logs -f docextract`
- [ ] Disk space monitoring (PDFs accumulate)
- [ ] API cost tracking enabled

### Performance
- [ ] nginx gzip compression enabled
- [ ] Static files cached
- [ ] SSE keepalive working (15s interval)
- [ ] Docker resource limits set

---

## Custom Domain (Optional)

If client has their own domain (e.g., `docs.clientcompany.com`):

1. **Add DNS A Record**
   ```
   Type: A
   Name: docs
   Value: YOUR_SERVER_IP
   TTL: 300
   ```

2. **Update nginx config**
   ```nginx
   server_name docs.clientcompany.com;
   ```

3. **Get SSL Certificate (Let's Encrypt)**
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d docs.clientcompany.com
   ```

---

## Troubleshooting

### Logs
```bash
# All logs
docker-compose -f docker/docker-compose.prod.yml logs -f

# Just DocExtract
docker logs -f docextract

# nginx
docker logs -f docextract-nginx
```

### Health Check
```bash
curl http://localhost:8000/health | jq .
```

### Reset Everything
```bash
docker-compose -f docker/docker-compose.prod.yml down -v
docker system prune -af
docker-compose -f docker/docker-compose.prod.yml up -d
```

---

## Updating

### Manual Update
```bash
cd /opt/docextract
git pull origin main
docker-compose down
docker-compose up -d --build
```

### Auto-update (GitHub Actions)
Just push to GitHub — deploys automatically!

---

## Cost Estimates

| Service | Monthly Cost |
|---------|-------------|
| VPS (2GB RAM, DigitalOcean) | $12 |
| DuckDNS | Free |
| Claude API (1000 docs) | $42 |
| **Total** | **~$54/month** |

**Compare:** Manual data entry at $15/hr = $2,500-7,500/month for 1000 docs.

---

## Demo Setup (5 minutes)

**Fastest way to show client:**

```bash
# Your laptop/desktop
git clone https://github.com/YOUR_USERNAME/docextract.git
cd docextract

# Add API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Run
python run.py

# Open browser
open http://localhost:8000
```

Share your screen → drag PDF → watch live extraction. No deployment needed for initial pitch!

---

## Support

- Issues: https://github.com/YOUR_USERNAME/docextract/issues
- Docs: README.md
- Health: http://YOUR_DOMAIN/health
