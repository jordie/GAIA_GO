# Production Deployment Guide

This guide covers deploying architect-go to production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Configuration](#configuration)
6. [Database Setup](#database-setup)
7. [Health Checks](#health-checks)
8. [Monitoring](#monitoring)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

- Go 1.20+
- Docker & Docker Compose (for containerized deployment)
- Kubernetes 1.20+ (for K8s deployment)
- PostgreSQL 12+ or SQLite 3.30+
- kubectl configured to access your cluster

## Local Development

### Build the Application

```bash
# Clone the repository
git clone https://github.com/jordie/architect.git
cd architect/architect-go

# Build the binary
go build -o architect-go ./cmd/main.go

# Run locally
./architect-go
```

### Using Docker Compose

```bash
# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f architect-go

# Stop services
docker-compose down
```

## Docker Deployment

### Build Docker Image

```bash
# Build production image
docker build -f deploy/Dockerfile.prod -t architect-go:latest .

# Tag for registry
docker tag architect-go:latest myregistry.azurecr.io/architect-go:latest

# Push to registry
docker push myregistry.azurecr.io/architect-go:latest
```

### Run Docker Container

```bash
# Run container
docker run -d \
  -p 8080:8080 \
  -e DATABASE_URL="sqlite:///data/architect.db" \
  -e LOG_LEVEL="info" \
  -v $(pwd)/data:/data \
  --name architect-go \
  architect-go:latest

# Check logs
docker logs -f architect-go

# Stop container
docker stop architect-go
```

## Kubernetes Deployment

### Prerequisites

1. **Kubernetes cluster access**
   ```bash
   # Verify connection
   kubectl cluster-info
   kubectl get nodes
   ```

2. **Namespace setup** (optional)
   ```bash
   kubectl create namespace architect
   kubectl set current-context architect
   ```

3. **Secrets configuration**
   ```bash
   # Update database URL in architect-go-secret.yaml
   # Then create secret
   kubectl apply -f deploy/kubernetes/architect-go-secret.yaml
   ```

### Deploy to Kubernetes

```bash
# Apply manifests in order
kubectl apply -f deploy/kubernetes/architect-go-configmap.yaml
kubectl apply -f deploy/kubernetes/architect-go-secret.yaml
kubectl apply -f deploy/kubernetes/architect-go-deployment.yaml
kubectl apply -f deploy/kubernetes/architect-go-service.yaml
kubectl apply -f deploy/kubernetes/architect-go-hpa.yaml

# Verify deployment
kubectl get deployments
kubectl get pods
kubectl get services

# Check pod status
kubectl describe pod <pod-name>

# View logs
kubectl logs -f deployment/architect-go
```

### Expose Service

```bash
# Using port forwarding (development)
kubectl port-forward svc/architect-go 8080:80

# Using LoadBalancer (production)
kubectl apply -f deploy/kubernetes/architect-go-service.yaml

# Get external IP
kubectl get svc architect-go-loadbalancer
```

### Update Deployment

```bash
# Update image
kubectl set image deployment/architect-go \
  architect-go=myregistry.azurecr.io/architect-go:v1.2.3

# Monitor rollout
kubectl rollout status deployment/architect-go

# Rollback if needed
kubectl rollout undo deployment/architect-go
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Server port |
| `ENVIRONMENT` | `development` | Environment (development/production) |
| `LOG_LEVEL` | `info` | Log level (debug/info/warn/error) |
| `DATABASE_URL` | - | Database connection string |
| `CACHE_ENABLED` | `true` | Enable caching layer |
| `SESSION_TIMEOUT` | `3600` | Session timeout in seconds |
| `METRICS_ENABLED` | `true` | Enable Prometheus metrics |

### Database Connection Strings

**SQLite**
```
sqlite:///data/architect.db
sqlite:///:memory:
```

**PostgreSQL**
```
postgres://user:password@host:5432/architect
postgresql://user:password@host:5432/architect?sslmode=require
```

**MySQL**
```
mysql://user:password@tcp(host:3306)/architect
```

## Database Setup

### PostgreSQL Setup

```bash
# Create database
CREATE DATABASE architect;

# Create user
CREATE USER architect_user WITH PASSWORD 'secure_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE architect TO architect_user;

# Connection string
postgres://architect_user:secure_password@localhost:5432/architect
```

### Migration

Migrations run automatically on application startup:

```go
// In cmd/main.go
db.AutoMigrate(
    &models.User{},
    &models.Project{},
    &models.Task{},
    // ... other models
)
```

## Health Checks

### Health Endpoints

**Basic Health Check**
```bash
curl http://localhost:8080/health
# Response: {"status":"healthy","timestamp":"2026-02-18T..."}
```

**Liveness Probe** (Kubernetes)
```bash
curl http://localhost:8080/health/liveness
# Response: {"alive":true,"timestamp":"2026-02-18T..."}
```

**Readiness Probe** (Kubernetes)
```bash
curl http://localhost:8080/health/readiness
# Response: {"ready":true,"timestamp":"2026-02-18T...","components":{"database":true,"cache":true}}
```

**Detailed Health**
```bash
curl http://localhost:8080/health/detailed
# Full system status with metrics
```

## Monitoring

### Prometheus Integration

**Metrics Endpoint**
```bash
curl http://localhost:8080/metrics
```

**Prometheus Configuration**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'architect-go'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
```

### Metrics Available

- `architect_requests_total` — Total requests by endpoint
- `architect_errors_total` — Total errors by endpoint
- `architect_latency_ms` — Request latency
- `architect_active_connections` — Database connections
- `architect_cache_hit_rate` — Cache hit percentage
- `architect_cache_size` — Cache size in bytes

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name>

# View logs
kubectl logs <pod-name>

# Check events
kubectl get events --sort-by='.lastTimestamp'
```

### Database Connection Issues

```bash
# Test database connectivity from pod
kubectl exec -it <pod-name> -- \
  nc -zv database-host 5432

# Check connection string in secrets
kubectl get secret architect-secrets -o yaml
```

### High Memory Usage

```bash
# Check pod metrics
kubectl top pod <pod-name>

# Adjust resource limits
kubectl set resources deployment architect-go \
  --limits=memory=1Gi,cpu=1000m
```

### Slow Response Times

```bash
# Check detailed health
curl http://localhost:8080/health/detailed

# Check metrics
curl http://localhost:8080/metrics

# Review database connections
kubectl logs <pod-name> | grep "connection pool"
```

## Scaling

### Manual Scaling

```bash
# Scale to N replicas
kubectl scale deployment architect-go --replicas=5

# Check status
kubectl get deployment architect-go
```

### Automatic Scaling

Horizontal Pod Autoscaler automatically scales based on CPU/memory:

```bash
# Apply HPA
kubectl apply -f deploy/kubernetes/architect-go-hpa.yaml

# Monitor scaling
kubectl get hpa architect-go-hpa -w
```

## Backup & Recovery

### Database Backup

**PostgreSQL**
```bash
# Backup
pg_dump -U architect_user -d architect > backup.sql

# Restore
psql -U architect_user -d architect < backup.sql
```

**SQLite**
```bash
# Backup
cp data/architect.db backup/architect.db

# Restore
cp backup/architect.db data/architect.db
```

### PVC Backup (Kubernetes)

```bash
# Create snapshot
kubectl exec <pod-name> -- \
  tar czf - /data | tar xzf - -C backup/
```

## Security Considerations

1. **Secrets Management**
   - Use external secrets (Vault, AWS Secrets Manager)
   - Never commit actual secrets to git

2. **TLS/HTTPS**
   - Use cert-manager for automatic certificates
   - Enable HTTPS in production

3. **Network Policies**
   - Restrict ingress/egress traffic
   - Use service mesh (Istio) for advanced routing

4. **RBAC**
   - Minimize service account permissions
   - Use role-based access control

## Production Checklist

- [ ] Database configured and migrated
- [ ] Environment variables set
- [ ] Secrets secured (not in git)
- [ ] TLS/HTTPS configured
- [ ] Logging aggregated (ELK, Splunk, etc.)
- [ ] Monitoring enabled (Prometheus/Grafana)
- [ ] Alerting configured
- [ ] Backup strategy in place
- [ ] Disaster recovery tested
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Documentation reviewed

## Support & Issues

For issues or questions:
1. Check logs: `kubectl logs deployment/architect-go`
2. Check health: `curl http://localhost:8080/health/detailed`
3. Review metrics: `curl http://localhost:8080/metrics`
4. Check documentation: See MONITORING.md, TROUBLESHOOTING.md
