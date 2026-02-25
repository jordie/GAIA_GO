# Tailscale Network Configuration

## Network Information

**Primary Tailscale IP**: `100.112.58.92`

All services are configured to be accessible via Tailscale network for secure remote access.

## Service Endpoints

### Development Team (Go Wrapper)
- **API Server**: `http://100.112.58.92:8151`
- **Main Dashboard**: `http://100.112.58.92:8151`
- **Interactive Control**: `http://100.112.58.92:8151/interactive`
- **Performance**: `http://100.112.58.92:8151/performance`
- **Database**: `http://100.112.58.92:8151/database`
- **Replay**: `http://100.112.58.92:8151/replay`
- **Query Builder**: `http://100.112.58.92:8151/query`

### Educational Apps
- **DEV Environment**: `https://100.112.58.92:5051`
- **QA Environment**: `https://100.112.58.92:5052`
- **PROD Environment**: `https://100.112.58.92:5063`

### Architecture Dashboard
- **Dashboard**: `https://100.112.58.92:5051/architecture/`

## Benefits of Tailscale Integration

1. **Remote Access**: Access dashboards from any device on your Tailscale network
2. **Security**: Encrypted mesh network, no port forwarding needed
3. **Simplicity**: No VPN configuration, automatic peer discovery
4. **Multi-device**: Work from laptop, desktop, tablet, or phone
5. **Team Collaboration**: Share access with team members via Tailscale

## Accessing from Other Devices

### From Laptop/Desktop

```bash
# Open dashboards
open http://100.112.58.92:8151
open https://100.112.58.92:5051

# API calls
curl http://100.112.58.92:8151/api/agents | jq
curl -k https://100.112.58.92:5051/api/config | jq
```

### From Mobile

Simply open these URLs in your mobile browser:
- Team Dashboard: http://100.112.58.92:8151
- Apps Dashboard: https://100.112.58.92:5051

(Accept self-signed certificate warning for HTTPS endpoints)

### From Tablet

Same as mobile - all dashboards are responsive and work on tablets.

## Firewall Configuration

The API server binds to `0.0.0.0:8151` to accept connections from all interfaces, allowing Tailscale access.

```bash
# Server listens on all interfaces
./apiserver --host 0.0.0.0 --port 8151
```

## Network Diagnostics

### Check Tailscale Status

```bash
# Show Tailscale IP
tailscale ip -4

# Show all Tailscale peers
tailscale status

# Test connectivity
ping 100.112.58.92
```

### Check API Server

```bash
# From local machine
curl http://100.112.58.92:8151/api/health

# From remote Tailscale device
curl http://100.112.58.92:8151/api/health
```

### Port Verification

```bash
# Check if port is listening
lsof -i :8151

# Expected output:
# apiserver <PID> user  TCP *:8151 (LISTEN)
```

## Troubleshooting

### Cannot Connect from Remote Device

1. **Check Tailscale is running**:
   ```bash
   tailscale status
   ```

2. **Verify device is on network**:
   ```bash
   tailscale ping <device-name>
   ```

3. **Check firewall rules** (macOS):
   ```bash
   # Allow incoming on port 8151
   # System Preferences > Security & Privacy > Firewall > Firewall Options
   ```

4. **Restart API server**:
   ```bash
   pkill apiserver
   cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/go_wrapper
   ./apiserver --host 0.0.0.0 --port 8151 --db data/dev_team.db
   ```

### Slow Performance

1. **Check Tailscale connection quality**:
   ```bash
   tailscale netcheck
   ```

2. **Use direct connection if available**:
   - Tailscale attempts direct connections (DERP relay only as fallback)
   - Check status for "direct" vs "relay" connections

### Certificate Warnings (HTTPS endpoints)

The educational apps use self-signed certificates:
- **Browser**: Type `thisisunsafe` on warning page (Chrome)
- **curl**: Use `-k` flag: `curl -k https://100.112.58.92:5051`

## Security Best Practices

1. **Restrict Tailscale ACLs**: Limit which devices can access which services
2. **Use HTTPS**: Where available (educational apps)
3. **Monitor Access**: Check API server logs regularly
4. **Update Regularly**: Keep Tailscale client updated
5. **Revoke Access**: Remove devices from Tailscale network when no longer needed

## Example ACL Configuration

In Tailscale admin console, you can restrict access:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["team-member@example.com"],
      "dst": ["100.112.58.92:8151", "100.112.58.92:5051"]
    }
  ]
}
```

## Integration with Auto-Confirm

Auto-confirm worker monitors tmux sessions and works seamlessly with Tailscale network. Remote access to dashboards doesn't affect local automation.

## Future Enhancements

- [ ] Add Tailscale Funnel for public sharing
- [ ] Configure Magic DNS for friendly names
- [ ] Set up Tailscale SSH for secure remote access
- [ ] Add Tailscale serve for simplified configuration

---

**Network**: Tailscale Private Network
**Primary Node**: 100.112.58.92
**Last Updated**: 2026-02-10
