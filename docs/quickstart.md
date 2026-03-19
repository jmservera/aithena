# Aithena Production Quickstart Guide

This guide provides step-by-step instructions for deploying Aithena in a production environment using the official release package.

## Prerequisites

- Linux server with Docker Engine 20.10+ and Docker Compose v2+
- At least 8 GB RAM (16 GB recommended)
- 50 GB available disk space
- Python 3.11+ (for running the installer)
- Network access to GitHub Container Registry (ghcr.io) for pulling images

## Installation Steps

### 1. Extract the Release Package

```bash
tar -xzf aithena-v{version}-release.tar.gz
cd aithena-v{version}-release
```

### 2. Run the Installer

The installer will guide you through the initial setup and generate secure secrets:

```bash
python3 -m installer
```

The installer will prompt you for:
- **Book library path**: Directory containing your PDF documents (e.g., `/data/booklibrary`)
- **Admin username**: Administrator account username (default: `admin`)
- **Admin password**: Secure password for the administrator account
- **Public origin URL**: The URL where Aithena will be accessible (e.g., `http://your-domain.com` or `https://books.example.com`)

The installer automatically generates:
- `.env` file with secure JWT secret, RabbitMQ credentials, and Redis password
- SQLite authentication database at `~/.local/share/aithena/auth/users.db`

**Important**: The `.env` file contains sensitive credentials. Ensure proper file permissions:

```bash
chmod 600 .env
```

### 3. Create Required Directories

Create the Docker volume mount points:

```bash
sudo mkdir -p /source/volumes/{rabbitmq-data,redis,solr-data,solr-data2,solr-data3}
sudo mkdir -p /source/volumes/{zoo-data1,zoo-data2,zoo-data3}/{logs,data,datalog}
sudo mkdir -p /source/volumes/zoo-backup
```

Adjust ownership if needed:

```bash
sudo chown -R $USER:$USER /source/volumes
```

### 4. Start the Application

Pull the images and start all services:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### 5. Monitor Startup

Check service health:

```bash
docker compose -f docker-compose.prod.yml ps
```

View logs for a specific service:

```bash
docker compose -f docker-compose.prod.yml logs -f <service-name>
```

The startup sequence:
1. **Infrastructure**: Redis, RabbitMQ, ZooKeeper (30-60 seconds)
2. **SolrCloud**: Three Solr nodes join the ZooKeeper ensemble (60-90 seconds)
3. **Solr initialization**: Config upload and collection creation (30-60 seconds)
4. **Application services**: Embeddings server, search API, document processors (60-90 seconds)
5. **Frontend**: UI and nginx reverse proxy (30 seconds)

**Total startup time**: 3-5 minutes for a cold start.

### 6. Access the Application

Once all services are healthy:

- **Main UI**: `http://your-domain/`
- **Admin Dashboard**: `http://your-domain/admin/streamlit`
- **API Documentation**: `http://your-domain/api/docs`

Sign in with the admin credentials you configured during installation.

## Post-Installation Configuration

### Enable HTTPS with Let's Encrypt

To add TLS, use the SSL overlay:

```bash
# Create certbot volume directories
sudo mkdir -p /source/volumes/certbot-data/{conf,www}

# Start with SSL enabled
docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d

# Obtain the initial certificate
docker compose -f docker-compose.yml -f docker-compose.ssl.yml \
  run --rm certbot certonly --webroot -w /var/www/certbot \
  -d your.domain.com --agree-tos -m you@example.com

# Update src/nginx/default.conf with your domain's HTTPS server block
docker compose -f docker-compose.yml -f docker-compose.ssl.yml restart nginx
```

### Add Documents to the Library

Place PDF files in the configured book library path (e.g., `/data/booklibrary`). The `document-lister` service will automatically discover and queue them for indexing every 60 seconds.

Monitor indexing progress:

```bash
docker compose -f docker-compose.prod.yml logs -f document-indexer
```

### Configure Resource Limits

The production compose file includes default resource limits. Adjust these in `docker-compose.prod.yml` based on your workload:

- **Solr nodes**: 2 GB RAM each (adjust for large collections)
- **Embeddings server**: 2 GB RAM (adjust based on model size)
- **Redis**: 512 MB RAM (increase for large cache workloads)

After modifying limits, restart the affected service:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate <service-name>
```

## Backup and Maintenance

### Backup Critical Data

Regularly back up these volumes:

- `/source/volumes/solr-data*` — Solr indexes
- `/source/volumes/zoo-data*` — ZooKeeper state
- `~/.local/share/aithena/auth/users.db` — Authentication database
- `.env` — Configuration and secrets

Example backup script:

```bash
#!/bin/bash
BACKUP_DIR=/backup/aithena/$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"

# Stop indexing to ensure consistency
docker compose -f docker-compose.prod.yml stop document-indexer document-lister

# Backup volumes
tar -czf "$BACKUP_DIR/solr-data.tar.gz" /source/volumes/solr-data*
tar -czf "$BACKUP_DIR/zoo-data.tar.gz" /source/volumes/zoo-data*
cp ~/.local/share/aithena/auth/users.db "$BACKUP_DIR/"
cp .env "$BACKUP_DIR/"

# Resume indexing
docker compose -f docker-compose.prod.yml start document-indexer document-lister
```

### Update to a New Release

1. Stop the current stack: `docker compose -f docker-compose.prod.yml down`
2. Extract the new release package
3. Copy your `.env` file to the new release directory
4. Pull updated images: `docker compose -f docker-compose.prod.yml pull`
5. Start the new version: `docker compose -f docker-compose.prod.yml up -d`

## Troubleshooting

### Services fail to start

Check logs for the failing service:

```bash
docker compose -f docker-compose.prod.yml logs <service-name>
```

Common issues:
- **Missing .env file**: Run `python3 -m installer` to generate configuration
- **Permission errors**: Check volume mount points in `/source/volumes`
- **Port conflicts**: Ensure ports 80, 443 are available

### SolrCloud cluster issues

Verify ZooKeeper ensemble health:

```bash
for port in 2181 2182 2183; do
  echo "Zoo node on port $port:"
  echo ruok | nc localhost $port
done
```

All nodes should respond with `imok`.

Check Solr cluster status:

```bash
docker compose -f docker-compose.prod.yml exec solr curl -s 'http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS&wt=json' | jq .
```

### Indexing not progressing

Check RabbitMQ queue status:

```bash
docker compose -f docker-compose.prod.yml exec rabbitmq rabbitmqctl list_queues
```

Verify `document-lister` is scanning the library:

```bash
docker compose -f docker-compose.prod.yml logs document-lister | grep "Scanning"
```

### Authentication issues

Verify the auth database exists:

```bash
ls -lh ~/.local/share/aithena/auth/users.db
```

Reset the admin password:

```bash
python3 -m installer --reset --admin-password "new-secure-password"
```

## Security Hardening

### Production Checklist

- [ ] Change all default passwords (run `python3 -m installer` to regenerate secrets)
- [ ] Restrict `.env` file permissions: `chmod 600 .env`
- [ ] Enable HTTPS with valid TLS certificates
- [ ] Configure firewall rules (allow only 80/443 from internet)
- [ ] Set `AUTH_ENABLED=true` (never disable in production)
- [ ] Keep Redis password-protected (`REDIS_PASSWORD` must be set)
- [ ] Use strong RabbitMQ credentials (never use `guest`)
- [ ] Regularly update Docker images: `docker compose pull && docker compose up -d`

### Network Security

The production compose file exposes only ports 80 and 443. All inter-service communication happens on the internal Docker network.

For additional security, consider:
- Placing Aithena behind a reverse proxy (e.g., Traefik, Caddy)
- Using Docker secrets instead of environment variables for sensitive data
- Enabling Docker Content Trust for image verification
- Implementing rate limiting at the nginx level

## Support

For issues, feature requests, or questions:
- GitHub Issues: https://github.com/jmservera/aithena/issues
- Documentation: https://github.com/jmservera/aithena/tree/main/docs

## License

Aithena is released under the MIT License. See the LICENSE file in the repository for details.
