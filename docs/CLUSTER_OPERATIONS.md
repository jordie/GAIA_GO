# GAIA_GO Cluster Operations Guide

Complete guide for managing GAIA_GO's Raft cluster in production, including node management, monitoring, snapshot operations, and disaster recovery.

## Table of Contents

1. [Cluster Architecture](#cluster-architecture)
2. [Node Management](#node-management)
3. [Snapshot Management](#snapshot-management)
4. [Node Discovery](#node-discovery)
5. [Monitoring & Health](#monitoring--health)
6. [Disaster Recovery](#disaster-recovery)
7. [Troubleshooting](#troubleshooting)

---

## Cluster Architecture

### Raft Consensus Protocol

GAIA_GO uses Raft consensus for distributed coordination across 3+ nodes:

```
┌─────────────────────────────────────────────────────┐
│                    Raft Cluster                     │
│  ┌──────────────┬──────────────┬──────────────────┐ │
│  │   Node 1     │   Node 2     │   Node 3         │ │
│  │  (Leader)    │  (Follower)  │  (Follower)      │ │
│  └──────────────┴──────────────┴──────────────────┘ │
│         ↓              ↓              ↓             │
│    Log Replication ← Consensus → Health Checks     │
└─────────────────────────────────────────────────────┘
```

### Key Components

1. **ClusterManager**: Manages peer information and state
2. **SnapshotManager**: Handles snapshots and log compaction
3. **DiscoveryManager**: Discovers and tracks cluster nodes
4. **Health Monitoring**: Tracks peer heartbeats and state

---

## Node Management

### Adding a Node to the Cluster

#### Via API

```bash
# Request to add node-4 to the cluster (must be sent to current leader)
curl -X POST http://leader:8080/api/cluster/peers \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-4",
    "address": "node-4.example.com:8300"
  }'
```

#### Via CLI

```bash
# Using cluster join command
./gaia_go --cluster-join \
  --node-id node-4 \
  --address node-4.example.com:8300 \
  --leader-address node-1.example.com:8080
```

#### Verification

```bash
# Check cluster status to verify node joined
curl http://leader:8080/api/cluster/status | jq .

# Expected output shows all 4 nodes
{
  "nodes": [
    {"id": "node-1", "state": "healthy", "is_leader": true},
    {"id": "node-2", "state": "healthy", "is_leader": false},
    {"id": "node-3", "state": "healthy", "is_leader": false},
    {"id": "node-4", "state": "healthy", "is_leader": false}
  ],
  "term": 42,
  "peer_count": 4
}
```

### Removing a Node from the Cluster

#### Safe Removal (Node Still Running)

```bash
# Ask node to gracefully remove itself
curl -X DELETE http://node-to-remove:8080/api/cluster/self

# Or remove from leader
curl -X DELETE http://leader:8080/api/cluster/peers/node-4
```

#### Emergency Removal (Node Down)

```bash
# Force removal of a dead node (only from leader)
curl -X DELETE http://leader:8080/api/cluster/peers/node-4?force=true

# WARNING: Can cause split-brain if node comes back up
# After recovery, delete node's raft data and rejoin as new node
```

### Viewing Cluster Status

```bash
# Full cluster status
curl http://any-node:8080/api/cluster/status | jq .

# Detailed peer information
curl http://any-node:8080/api/cluster/peers | jq .

# Individual peer status
curl http://any-node:8080/api/cluster/peers/node-2 | jq .
```

---

## Snapshot Management

### Automatic Snapshots

Configured via environment variables:

```bash
RAFT_SNAPSHOT_INTERVAL=120s  # Snapshot every 2 minutes if logs grow
RAFT_LOG_SIZE_THRESHOLD=1GB  # Take snapshot when logs exceed 1GB
```

### Manual Snapshots

```bash
# Request manual snapshot
curl -X POST http://leader:8080/api/cluster/snapshot

# Check snapshot status
curl http://any-node:8080/api/cluster/snapshot-status | jq .

# Expected response:
{
  "last_snapshot": "2026-02-25T10:30:00Z",
  "snapshot_count": 42,
  "average_snapshot_size_mb": 150,
  "log_entries_since_snapshot": 1023
}
```

### Snapshot Maintenance

#### List Snapshots

```bash
# View all snapshots
curl http://any-node:8080/api/cluster/snapshots | jq .

# Output:
[
  {
    "filename": "snapshot_5000_20260225103000.snap",
    "size_mb": 180,
    "created_at": "2026-02-25T10:30:00Z"
  },
  {
    "filename": "snapshot_4000_20260225100000.snap",
    "size_mb": 175,
    "created_at": "2026-02-25T10:00:00Z"
  }
]
```

#### Delete Old Snapshots

```bash
# Delete snapshots older than 7 days
curl -X DELETE "http://any-node:8080/api/cluster/snapshots?older_than=7d"

# Verify deletion
du -sh /app/data/snapshots/
```

### Log Compaction

Snapshots automatically compact logs:

```bash
# Check current log size
curl http://any-node:8080/api/cluster/log-info | jq .

# Output:
{
  "first_index": 950,      # Logs before this are compacted
  "last_index": 5000,      # Latest log entry
  "log_size_bytes": 524288000
}
```

---

## Node Discovery

### Static Configuration

For simple deployments, use static node discovery:

```bash
# Set environment variable with all known nodes
export CLUSTER_DISCOVERY_NODES="node-1:8300,node-2:8300,node-3:8300"
```

### Dynamic Discovery

For cloud deployments, use DNS or Consul:

#### DNS Discovery

```bash
# All nodes must have consistent hostname
# e.g., node-0.gaia-go.default.svc.cluster.local

export CLUSTER_DISCOVERY_TYPE=dns
export CLUSTER_DISCOVERY_DOMAIN=gaia-go.default.svc.cluster.local
export CLUSTER_DISCOVERY_PORT=8300
export CLUSTER_DISCOVERY_REFRESH_RATE=30s
```

#### Consul Discovery

```bash
export CLUSTER_DISCOVERY_TYPE=consul
export CONSUL_ADDR=consul.example.com:8500
export CONSUL_DATACENTER=dc1
```

### Verification

```bash
# Check discovered nodes
curl http://any-node:8080/api/cluster/discovered-nodes | jq .

# Should show all cluster members
[
  {"id": "node-1", "hostname": "node-1.example.com", "raft_port": 8300},
  {"id": "node-2", "hostname": "node-2.example.com", "raft_port": 8300},
  {"id": "node-3", "hostname": "node-3.example.com", "raft_port": 8300}
]
```

---

## Monitoring & Health

### Cluster Metrics

```bash
# Get cluster health overview
curl http://any-node:8080/api/cluster/health | jq .

# Response:
{
  "cluster_status": "healthy",
  "leader_id": "node-1",
  "term": 42,
  "peer_count": 3,
  "healthy_peers": 3,
  "degraded_peers": 0,
  "unhealthy_peers": 0,
  "last_log_index": 5000,
  "last_snapshot": "2026-02-25T10:30:00Z"
}
```

### Per-Node Metrics

```bash
# Monitor a specific node
curl http://node-2:8080/api/cluster/metrics | jq .

# Response includes:
{
  "node_id": "node-2",
  "is_leader": false,
  "leader_id": "node-1",
  "term": 42,
  "last_heartbeat": "2026-02-25T10:35:12Z",
  "state": "healthy",
  "match_index": 5000,
  "next_index": 5001
}
```

### Prometheus Metrics

```bash
# Scrape Prometheus metrics for Grafana
curl http://any-node:9090/metrics | grep raft_

# Key metrics:
# - raft_leader_elections_total
# - raft_log_index (last/first)
# - raft_applied_index
# - raft_state_machine_ops_total
```

### Setting Up Alerts

```yaml
# Prometheus alert rules (alerting/raft_alerts.yml)
groups:
  - name: cluster
    rules:
      - alert: LeaderElection
        expr: increase(raft_leader_elections_total[5m]) > 0
        annotations:
          summary: "Raft leader election in progress"

      - alert: HighLogSize
        expr: raft_log_size_bytes > 1e9
        annotations:
          summary: "Raft log size exceeds 1GB"

      - alert: UnhealthyPeers
        expr: raft_unhealthy_peers > 0
        annotations:
          summary: "{{ $value }} unhealthy peers"
```

---

## Disaster Recovery

### Node Failure Scenarios

#### Scenario 1: Follower Node Fails

```
Timeline:
1. Node-2 stops responding (heartbeat timeout)
2. Leader marks node-2 as unhealthy after 30 seconds
3. Cluster continues with 2/3 consensus
4. Node-2 comes back online and rejoins automatically
```

**Recovery**:
- No action needed
- Node will catch up via log replication
- Status becomes "healthy" when caught up

#### Scenario 2: Leader Node Fails

```
Timeline:
1. Followers don't receive heartbeat for 300ms
2. New election is triggered
3. Node-2 or Node-3 elected as new leader (takes ~150ms)
4. Cluster continues operating with new leader
```

**Recovery**:
```bash
# Old leader comes back up - it rejoins as follower
curl http://old-leader:8080/api/cluster/status | jq .leader_id
# Shows new leader: "node-2"

# Can optionally force new election to rebalance
curl -X POST http://current-leader:8080/api/cluster/force-election
```

#### Scenario 3: Minority Partition (2 nodes in 3-node cluster)

```
Timeline:
1. Network partition isolates 1 node (node-3)
2. Majority (2 nodes) continue operating
3. Minority (1 node) stops processing writes
4. Network heals, node-3 rejoins
```

**Recovery**:
```bash
# Check if cluster is healthy
curl http://any-node:8080/api/cluster/health | jq .cluster_status

# If "unhealthy", check partition status
curl http://any-node:8080/api/cluster/peers | jq '.[] | {id, state}'

# Wait for automatic rejoining (up to 2 minutes)
# If no recovery, manually rejoin:
curl -X POST http://isolated-node:8080/api/cluster/rejoin \
  -d '{"leader_address": "node-1:8080"}'
```

### Point-in-Time Recovery

If data corruption is detected:

```bash
# 1. Stop all cluster nodes
for node in node-1 node-2 node-3; do
  ssh $node "systemctl stop gaia_go"
done

# 2. Check available snapshots
ssh node-1 "ls -lah /app/data/snapshots/"

# 3. Restore from backup
# (See DATABASE_OPTIMIZATION.md for detailed backup recovery)
ssh node-1 "pg_restore --dbname=gaia_go /backups/gaia_go_full_20260224.dump"

# 4. Delete node's raft data (will be rebuilt from snapshot)
ssh node-1 "rm -rf /app/data/raft_logs"

# 5. Start first node
ssh node-1 "systemctl start gaia_go"

# 6. Verify leader election
sleep 5
curl http://node-1:8080/api/cluster/status | jq .leader_id

# 7. Start remaining nodes (they'll catch up)
for node in node-2 node-3; do
  ssh $node "systemctl start gaia_go"
done

# 8. Verify all nodes healthy
curl http://node-1:8080/api/cluster/health | jq .
```

### Bootstrapping a New Cluster

If all nodes are lost and need to be rebuilt:

```bash
# 1. Restore database from backup
pg_restore --dbname=gaia_go /backups/gaia_go_full_latest.dump

# 2. Start first node in bootstrap mode
CLUSTER_BOOTSTRAP=true ./gaia_go --node-id node-1

# Wait for leader election (~300ms)
sleep 1

# 3. Verify node-1 is leader
curl http://node-1:8080/api/cluster/status | jq .

# 4. Start remaining nodes normally
# (They'll discover and join node-1 via configured discovery)
./gaia_go --node-id node-2
./gaia_go --node-id node-3

# 5. Verify all nodes healthy
curl http://node-1:8080/api/cluster/health | jq .cluster_status
```

---

## Troubleshooting

### Symptom: Cluster Not Electing Leader

```bash
# 1. Check node connectivity
for node in node-1 node-2 node-3; do
  curl -s http://$node:8080/health | jq .status
done

# 2. Check if all nodes are in the cluster
curl http://any-node:8080/api/cluster/peers | jq 'length'
# Should return 3

# 3. Check Raft logs for errors
docker logs gaia_node_1 | grep -i raft | tail -20

# 4. If stuck, force leader election
curl -X POST http://node-1:8080/api/cluster/force-election
```

### Symptom: High Replication Lag

```bash
# Check replication status
curl http://leader:8080/api/cluster/peers | jq '.[] | {id, match_index, next_index}'

# If lag > 1000 entries, trigger snapshot:
curl -X POST http://leader:8080/api/cluster/snapshot

# Monitor catch-up
curl http://leader:8080/api/cluster/peers | jq '.[] | {id, match_index}' | watch -n 1
```

### Symptom: Network Partition

```bash
# Check if cluster is quorate (has majority)
curl http://any-node:8080/api/cluster/status | jq .peer_count

# If stuck in minority partition, split-brain recovery:
curl -X POST http://minority-node:8080/api/cluster/rejoin \
  -d '{"leader_address": "majority-leader:8080"}'
```

### Symptom: Node Won't Rejoin After Restart

```bash
# 1. Clear corrupted Raft state
docker exec gaia_node_2 rm -rf /app/data/raft_logs

# 2. Delete snapshot if necessary (forces full replay)
docker exec gaia_node_2 rm -rf /app/data/snapshots

# 3. Restart node (it will rejoin from scratch)
docker-compose restart gaia_node_2

# 4. Monitor catch-up
curl http://leader:8080/api/cluster/peers | jq '.[] | {id, match_index}'
```

---

## Operational Checklist

### Daily
- [ ] Verify all 3 nodes healthy: `curl http://any:8080/api/cluster/health`
- [ ] Check leader is stable: `curl http://any:8080/api/cluster/status | jq .leader_id`
- [ ] Monitor replication lag: `curl http://leader:8080/api/cluster/peers | jq '.[] | .match_index'`

### Weekly
- [ ] Review Prometheus metrics for leader elections
- [ ] Check log size: `curl http://any:8080/api/cluster/log-info | jq .log_size_bytes`
- [ ] Verify snapshots are being taken
- [ ] Test node removal and addition

### Monthly
- [ ] Test failover by stopping leader
- [ ] Verify backup restoration works
- [ ] Review cluster logs for errors
- [ ] Analyze Raft state machine performance

---

## Configuration Reference

### Raft Consensus Settings

```bash
RAFT_HEARTBEAT_TIMEOUT=150ms   # Follower heartbeat timeout
RAFT_ELECTION_TIMEOUT=300ms    # Election timeout
RAFT_SNAPSHOT_INTERVAL=120s    # How often to try snapshots
RAFT_LOG_SIZE_THRESHOLD=1GB    # Size that triggers snapshots
```

### Network Settings

```bash
CLUSTER_BIND_ADDR=0.0.0.0:8300        # Local bind address
CLUSTER_ADVERTISE_ADDR=node-1:8300    # Advertised address to peers
CLUSTER_RPC_TIMEOUT=5s                # RPC timeout
```

### Discovery Settings

```bash
CLUSTER_DISCOVERY_TYPE=static         # static, dns, consul
CLUSTER_DISCOVERY_NODES=...           # Comma-separated node list
CLUSTER_DISCOVERY_REFRESH_RATE=30s    # How often to refresh
```

---

## Additional Resources

- [Raft Consensus Algorithm](https://raft.github.io/)
- [hashicorp/raft Documentation](https://pkg.go.dev/github.com/hashicorp/raft)
- [Cluster Membership Guide](https://raft.github.io/raft-tpc/chapter-4.html)
- [Consensus Algorithms](https://en.wikipedia.org/wiki/Consensus_(computer_science))
