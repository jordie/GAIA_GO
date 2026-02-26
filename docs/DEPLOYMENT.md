# GAIA_GO Production Deployment Guide

This guide covers deploying GAIA_GO to production with a 3-node Raft cluster, PostgreSQL with TimescaleDB, and nginx load balancing.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Docker Compose)](#quick-start-docker-compose)
3. [Production Deployment (Kubernetes)](#production-deployment-kubernetes)
4. [Production Deployment (VMs)](#production-deployment-vms)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Maintenance](#maintenance)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Software Requirements

- **Docker**: 20.10+ (for containerized deployment)
- **Docker Compose**: 2.0+ (for local multi-node testing)
- **PostgreSQL**: 14+ with TimescaleDB extension
- **Kubernetes**: 1.24+ (optional, for K8s deployment)
- **Helm**: 3.0+ (optional, for K8s Helm charts)
- **curl**: For health checks and testing

### Hardware Requirements

**Minimum (Development/Testing)**:
- CPU: 2 cores
- RAM: 4 GB
- Disk: 20 GB SSD

**Recommended (Production)**:
- CPU: 4+ cores per node
- RAM: 8+ GB per node
- Disk: 100+ GB SSD per node
- Network: 1 Gbps minimum, 10 Gbps recommended

### Network Requirements

- Port 8080: API traffic (HTTP/HTTPS)
- Port 8300: Raft inter-node communication (internal)
- Port 5432: PostgreSQL (internal)
- Port 6379: Redis (internal, optional)
- Port 3000: Grafana (monitoring)
- Port 9090: Prometheus (metrics)

---

## Quick Start (Docker Compose)

### 1. Generate Self-Signed Certificates

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/server.key -out certs/server.crt -days 365 -nodes \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### 2. Start the 3-Node Cluster

```bash
# Build the Docker image
docker build -f Dockerfile.prod -t gaia_go:1.0.0 .

# Start the cluster with docker-compose
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy (2-3 minutes)
docker-compose -f docker-compose.prod.yml ps
```

### 3. Verify Cluster Health

```bash
# Check all nodes are running
docker-compose -f docker-compose.prod.yml ps

# Check Raft cluster status
curl -s http://localhost:8080/api/cluster/status | jq .

# Check database
docker exec gaia_postgres psql -U gaia_user -d gaia_go -c "\dt"

# Check metrics collection
curl -s http://localhost:8080/api/dashboard/health | jq .
```

### 4. Test Load Balancing

```bash
# Make a request - should be load-balanced across nodes
for i in {1..3}; do
  echo "Request $i:"
  curl -s http://localhost/api/cluster/status | jq '.node_id'
done

# Access dashboard
open http://localhost:3000  # Grafana
open https://localhost      # GAIA_GO API
```

### 5. Stop the Cluster

```bash
docker-compose -f docker-compose.prod.yml down

# Remove volumes (WARNING: deletes data)
docker-compose -f docker-compose.prod.yml down -v
```

---

## Production Deployment (Kubernetes)

### 1. Create Kubernetes Manifests

Create `k8s/gaia-namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: gaia-go
```

Create `k8s/gaia-configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gaia-config
  namespace: gaia-go
data:
  LOG_LEVEL: "info"
  CLUSTER_ENABLED: "true"
  USABILITY_METRICS_ENABLED: "true"
  FRUSTRATION_DETECTION_ENABLED: "true"
```

Create `k8s/gaia-statefulset.yaml`:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: gaia-go
  namespace: gaia-go
spec:
  serviceName: gaia-go
  replicas: 3
  selector:
    matchLabels:
      app: gaia-go
  template:
    metadata:
      labels:
        app: gaia-go
    spec:
      containers:
      - name: gaia-go
        image: gaia_go:1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - name: api
          containerPort: 8080
          protocol: TCP
        - name: raft
          containerPort: 8300
          protocol: TCP
        env:
        - name: CLUSTER_NODE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: CLUSTER_ADVERTISE_ADDR
          value: "$(CLUSTER_NODE_ID).gaia-go.gaia-go.svc.cluster.local:8300"
        - name: DB_HOST
          value: postgres.gaia-go.svc.cluster.local
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        envFrom:
        - configMapRef:
            name: gaia-config
        livenessProbe:
          httpGet:
            path: /health
            port: api
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: api
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
        volumeMounts:
        - name: data
          mountPath: /app/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 50Gi
---
apiVersion: v1
kind: Service
metadata:
  name: gaia-go
  namespace: gaia-go
spec:
  clusterIP: None
  selector:
    app: gaia-go
  ports:
  - name: api
    port: 8080
    targetPort: 8080
  - name: raft
    port: 8300
    targetPort: 8300
---
apiVersion: v1
kind: Service
metadata:
  name: gaia-go-lb
  namespace: gaia-go
spec:
  type: LoadBalancer
  selector:
    app: gaia-go
  ports:
  - name: api
    port: 8080
    targetPort: 8080
    protocol: TCP
```

### 2. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/gaia-namespace.yaml

# Create PostgreSQL secret
kubectl create secret generic postgres-secret \
  -n gaia-go \
  --from-literal=username=gaia_user \
  --from-literal=password=<secure-password>

# Apply manifests
kubectl apply -f k8s/gaia-configmap.yaml
kubectl apply -f k8s/gaia-statefulset.yaml

# Wait for rollout
kubectl rollout status statefulset/gaia-go -n gaia-go

# Check pod status
kubectl get pods -n gaia-go -w
```

### 3. Access the Cluster

```bash
# Port forward to API
kubectl port-forward -n gaia-go svc/gaia-go-lb 8080:8080

# Get cluster status
curl -s http://localhost:8080/api/cluster/status | jq .
```

---

## Production Deployment (VMs)

### 1. Prepare Nodes

On each VM (node-1, node-2, node-3):

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install dependencies
sudo apt-get install -y docker.io docker-compose curl postgresql-client-14

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Create app directory
mkdir -p /opt/gaia_go
cd /opt/gaia_go
```

### 2. Copy Deployment Files

```bash
# Copy docker-compose, Dockerfile, and configs to each node
scp docker-compose.prod.yml node-1:/opt/gaia_go/
scp Dockerfile.prod node-1:/opt/gaia_go/
scp nginx.conf node-1:/opt/gaia_go/
# ... repeat for node-2 and node-3
```

### 3. Configure and Start Each Node

On node-1:

```bash
cd /opt/gaia_go
docker-compose -f docker-compose.prod.yml up -d
```

On node-2 and node-3:

```bash
cd /opt/gaia_go
# Modify docker-compose.prod.yml to point to node-1's postgres
# Change postgres service to external: postgres://node-1:5432
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Configure Load Balancer

On a dedicated load balancer VM or cloud LB:

```bash
# Install nginx
sudo apt-get install -y nginx

# Copy nginx config
sudo cp nginx.conf /etc/nginx/nginx.conf

# Generate SSL certificates
sudo mkdir -p /etc/nginx/certs
sudo openssl req -x509 -newkey rsa:4096 \
  -keyout /etc/nginx/certs/server.key \
  -out /etc/nginx/certs/server.crt \
  -days 365 -nodes

# Start nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## Configuration

### Environment Variables

Create a `.env` file in the deployment directory:

```bash
# Cluster Configuration
CLUSTER_ENABLED=true
CLUSTER_NODE_ID=node-1
CLUSTER_BIND_ADDR=0.0.0.0:8300
CLUSTER_ADVERTISE_ADDR=node-1.example.com:8300
CLUSTER_DISCOVERY_NODES=node-1.example.com:8300,node-2.example.com:8300,node-3.example.com:8300

# Database
DB_HOST=postgres.example.com
DB_PORT=5432
DB_USER=gaia_user
DB_PASSWORD=<secure-password>
DB_NAME=gaia_go
DB_POOL_SIZE=20
DB_MAX_IDLE_CONNS=5

# Redis (optional)
REDIS_ADDR=redis.example.com:6379
REDIS_ENABLED=true

# Raft Settings
RAFT_HEARTBEAT_TIMEOUT=150ms
RAFT_ELECTION_TIMEOUT=300ms
RAFT_SNAPSHOT_INTERVAL=120s

# Session Coordination
SESSION_LEASE_TIMEOUT=30s
SESSION_HEARTBEAT_INTERVAL=10s
SESSION_MAX_CONCURRENT=100

# Task Queue
TASK_MAX_RETRIES=3
TASK_CLAIM_TIMEOUT=10m

# Usability Metrics
USABILITY_METRICS_ENABLED=true
FRUSTRATION_DETECTION_ENABLED=true
TEACHER_DASHBOARD_ENABLED=true

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
API_TLS_CERT=/app/certs/server.crt
API_TLS_KEY=/app/certs/server.key

# Logging
LOG_LEVEL=info
LOG_FORMAT=json

# Monitoring
METRICS_ENABLED=true
METRICS_PORT=9090
PROMETHEUS_ENABLED=true
```

---

## Monitoring

### Prometheus Scrape Config

Create `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'gaia-go'
    static_configs:
      - targets:
        - 'gaia-node-1:9090'
        - 'gaia-node-2:9090'
        - 'gaia-node-3:9090'

  - job_name: 'postgres'
    static_configs:
      - targets:
        - 'postgres:5432'
```

### Grafana Dashboards

Import pre-built dashboards:

1. **System Metrics**: CPU, Memory, Disk, Network
2. **Raft Cluster**: Leader election, log replication, snapshots
3. **GAIA_GO Metrics**: Session count, task throughput, error rates
4. **Database**: Query performance, connection pool, replication lag
5. **Teacher Dashboard**: Student frustration, interventions, classroom health

---

## Maintenance

### Database Backups

```bash
# Automated daily backup
0 2 * * * pg_dump -h postgres -U gaia_user gaia_go | gzip > /backups/gaia_go_$(date +\%Y\%m\%d).sql.gz

# Restore from backup
gunzip < /backups/gaia_go_20260225.sql.gz | psql -h postgres -U gaia_user gaia_go
```

### Cluster Rolling Updates

```bash
# Update one node at a time
for node in node-1 node-2 node-3; do
  ssh $node "cd /opt/gaia_go && docker-compose pull && docker-compose up -d"
  sleep 30  # Wait for node to stabilize
done
```

### Log Rotation

Configure logrotate for application logs:

```bash
# /etc/logrotate.d/gaia_go
/opt/gaia_go/logs/*.log {
  daily
  rotate 7
  compress
  delaycompress
  notifempty
  create 0644 app app
  sharedscripts
  postrotate
    docker kill --signal=USR1 gaia_node_1
  endscript
}
```

---

## Troubleshooting

### Cluster Not Forming

```bash
# Check node connectivity
docker exec gaia_node_1 curl -s http://gaia_node_2:8080/health

# Check Raft logs
docker logs gaia_node_1 | grep -i raft

# Manually bootstrap if needed
docker exec gaia_node_1 /app/gaia_go --bootstrap-cluster
```

### Database Connection Issues

```bash
# Test database connection
docker exec gaia_postgres psql -U gaia_user -d gaia_go -c "SELECT 1"

# Check connection pool
curl -s http://localhost:8080/metrics | grep "db_connections"
```

### High Latency

```bash
# Check metrics latency
curl -s http://localhost:8080/api/dashboard/health | jq '.latencies'

# Check database indexes
docker exec gaia_postgres psql -U gaia_user -d gaia_go -c "\di"

# Check slow queries
docker logs gaia_node_1 | grep "slow query"
```

### Leader Election Issues

```bash
# Force new leader election
curl -X POST http://localhost:8080/api/cluster/force-election

# Check current leader
curl -s http://localhost:8080/api/cluster/status | jq '.leader'
```

---

## Production Checklist

Before going live:

- [ ] All 3 nodes passing health checks
- [ ] PostgreSQL replication working
- [ ] Redis cache working (if enabled)
- [ ] nginx load balancer distributing traffic
- [ ] SSL certificates installed and valid
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards functional
- [ ] Backups scheduled and tested
- [ ] Log rotation configured
- [ ] Monitoring alerts configured
- [ ] Incident response plan documented
- [ ] On-call rotation established

---

## Support & Monitoring

### Useful Endpoints

- **Health**: `/health` - Basic health check
- **Cluster Status**: `/api/cluster/status` - Raft cluster info
- **Metrics**: `/api/dashboard/health` - System health
- **Prometheus**: `http://localhost:9090` - Metrics UI
- **Grafana**: `http://localhost:3000` - Dashboards (admin/admin)

### Common Issues & Solutions

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for detailed solutions.

---

## Next Steps

1. **Staging Deployment**: Deploy to staging environment first
2. **Load Testing**: Validate performance under load
3. **Teacher Training**: Train teachers on dashboard usage
4. **Gradual Rollout**: Start with 10% traffic, then 50%, then 100%
5. **Monitoring**: Watch metrics closely during rollout

For more information, see:
- [Architecture Guide](./ARCHITECTURE.md)
- [Configuration Reference](./CONFIG_REFERENCE.md)
- [Cluster Operations](./CLUSTER_OPERATIONS.md)
