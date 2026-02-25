#!/usr/bin/env python3
"""
Deployment Worker - Automated CI/CD Pipeline

Watches for git events and automatically deploys to appropriate environments:

TRIGGERS:
  - Merge to dev branch    → Deploy to DEV environment (port 5051)
  - Tag v*.*.* on dev      → Deploy to QA environment (port 5052)
  - Tag release-* on dev   → Deploy to PROD environment (port 5063)

DEPLOYMENT BANNER:
  During deployment, a banner is shown on the target environment
  via the /api/deployment/status endpoint.

Usage:
    python3 deploy_worker.py                    # Run worker daemon
    python3 deploy_worker.py --watch            # Watch mode (foreground)
    python3 deploy_worker.py deploy dev         # Manual deploy to dev
    python3 deploy_worker.py deploy qa v1.0.5   # Manual deploy to qa
    python3 deploy_worker.py status             # Show deployment status

Configuration:
    Edit ENVIRONMENTS dict below for ports and paths.
"""

import http.client
import json
import os
import re
import shutil
import signal
import ssl
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread

# Configuration
BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "deploy_state.json"
LOG_FILE = BASE_DIR / "deploy_worker.log"
PID_FILE = Path("/tmp/deploy_worker.pid")
POLL_INTERVAL = 10  # seconds

# Environment configuration
ENVIRONMENTS = {
    "dev": {
        "port": 5051,
        "branch": "dev",
        "trigger": "merge",  # Deploy on any merge to dev
        "host": "192.168.1.231",
        "path": str(BASE_DIR),
        "auto_restart": True,
    },
    "qa": {
        "port": 5052,
        "branch": "dev",
        "trigger": "tag",  # Deploy on version tags
        "tag_pattern": r"^v\d+\.\d+\.\d+$",  # v1.0.0, v1.2.3, etc.
        "host": "192.168.1.231",
        "path": str(BASE_DIR / "qa_data"),
        "auto_restart": True,
    },
    "prod": {
        "port": 5063,
        "branch": "dev",
        "trigger": "tag",
        "tag_pattern": r"^release-\d+\.\d+\.\d+$",  # release-1.0.0
        "host": "192.168.1.231",
        "path": str(BASE_DIR),
        "auto_restart": True,
        "require_approval": True,  # Extra safety for prod
    },
}

# Remote cluster nodes for deployment
CLUSTER_NODES = {
    "pinklapi": {
        "host": "100.108.134.121",
        "port": 7051,
        "ssh": "pinklapi",
        "path": "~/edu_apps",
        "environments": ["dev", "qa"],  # Which environments to deploy
        "enabled": True,
    },
    "helen": {
        "host": "192.168.1.172",
        "port": 7052,
        "ssh": "helen",
        "path": "~/edu_apps",
        "environments": ["dev"],  # Dev only for helen
        "enabled": True,
    },
    "macpro": {
        "host": "100.113.137.24",
        "port": 7053,
        "ssh": "macpro",
        "path": "~/edu_apps",
        "environments": ["prod"],  # Production node
        "enabled": False,  # Currently not reachable via Tailscale
    },
}

# Cluster deployment settings
CLUSTER_DEPLOY_ENABLED = True  # Master switch for cluster deployments
CLUSTER_DEPLOY_ASYNC = True  # Deploy to cluster in background


def log(message, level="INFO"):
    """Log message to file and stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")


def load_state():
    """Load deployment state."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"last_commit": {}, "last_tag": {}, "deployments": [], "active_deployment": None}


def save_state(state):
    """Save deployment state."""
    STATE_FILE.write_text(json.dumps(state, indent=2))


def run_cmd(cmd, cwd=None, timeout=300):
    """Run shell command."""
    result = subprocess.run(
        cmd, shell=True, cwd=cwd or BASE_DIR, capture_output=True, timeout=timeout
    )
    # Handle potential encoding issues
    try:
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
    except:
        stdout = str(result.stdout)
    try:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
    except:
        stderr = str(result.stderr)
    return result.returncode == 0, stdout, stderr


def get_current_commit(branch="dev"):
    """Get current commit hash for branch."""
    ok, out, _ = run_cmd(f"git rev-parse {branch}")
    return out if ok else None


def get_latest_tag():
    """Get latest tag."""
    ok, out, _ = run_cmd("git describe --tags --abbrev=0 2>/dev/null")
    return out if ok else None


def get_all_tags():
    """Get all tags sorted by version."""
    ok, out, _ = run_cmd("git tag --sort=-v:refname")
    return out.split("\n") if ok and out else []


def set_deployment_banner(env_name, message, status="deploying"):
    """
    Set deployment banner via API.
    This updates the /api/deployment/status endpoint.
    """
    state = load_state()
    state["active_deployment"] = {
        "environment": env_name,
        "message": message,
        "status": status,
        "started": datetime.now().isoformat(),
        "progress": 0,
    }
    save_state(state)

    # Also write to a file that the app can read
    banner_file = BASE_DIR / "deployment_banner.json"
    banner_file.write_text(json.dumps(state["active_deployment"], indent=2))

    log(f"Banner set for {env_name}: {message}")


def clear_deployment_banner():
    """Clear the deployment banner."""
    state = load_state()
    state["active_deployment"] = None
    save_state(state)

    banner_file = BASE_DIR / "deployment_banner.json"
    if banner_file.exists():
        banner_file.unlink()

    log("Deployment banner cleared")


def update_deployment_progress(progress, message=None):
    """Update deployment progress (0-100)."""
    state = load_state()
    if state.get("active_deployment"):
        state["active_deployment"]["progress"] = progress
        if message:
            state["active_deployment"]["message"] = message
        save_state(state)

        banner_file = BASE_DIR / "deployment_banner.json"
        banner_file.write_text(json.dumps(state["active_deployment"], indent=2))


def restart_server(env_name):
    """Restart the server for an environment."""
    env = ENVIRONMENTS.get(env_name)
    if not env:
        return False

    port = env["port"]
    log(f"Restarting server on port {port}...")

    # Kill existing process
    run_cmd(f"lsof -ti:{port} | xargs kill -9 2>/dev/null")
    time.sleep(2)

    # Start new process
    env_vars = f"USE_HTTPS=true APP_ENV={env_name} PORT={port}"
    log_path = BASE_DIR / f"{env_name}_server.log"

    cmd = f"{env_vars} nohup python3 unified_app.py > {log_path} 2>&1 &"
    ok, _, err = run_cmd(cmd)

    time.sleep(3)

    # Verify it started
    ok, out, _ = run_cmd(f"lsof -ti:{port}")
    if out:
        log(f"Server started on port {port} (PID: {out})")
        return True
    else:
        log(f"Failed to start server on port {port}", "ERROR")
        return False


def deploy_to_env(env_name, version=None, source_branch="dev"):
    """
    Deploy to an environment.

    Args:
        env_name: 'dev', 'qa', or 'prod'
        version: Tag version for qa/prod deployments
        source_branch: Branch to deploy from
    """
    env = ENVIRONMENTS.get(env_name)
    if not env:
        log(f"Unknown environment: {env_name}", "ERROR")
        return False

    state = load_state()

    # Check for prod approval
    if env.get("require_approval") and not os.environ.get("DEPLOY_APPROVED"):
        log(f"Production deployment requires approval!", "WARN")
        return False

    try:
        # Set banner
        msg = f"Deploying {version or source_branch} to {env_name.upper()}..."
        set_deployment_banner(env_name, msg, "deploying")

        log(f"Starting deployment to {env_name}")
        update_deployment_progress(10, "Fetching latest code...")

        # Fetch latest
        run_cmd("git fetch --all --tags")
        update_deployment_progress(20, "Checking out code...")

        # Checkout appropriate version
        if version:
            ok, _, err = run_cmd(f"git checkout {version}")
            if not ok:
                raise Exception(f"Failed to checkout {version}: {err}")
        else:
            run_cmd(f"git checkout {source_branch}")
            run_cmd("git pull --rebase")

        update_deployment_progress(40, "Running migrations...")

        # Run migrations if they exist
        migration_script = BASE_DIR / "migrations" / "run_migrations.py"
        if migration_script.exists():
            run_cmd(f"python3 {migration_script} {env_name}")

        update_deployment_progress(60, "Syncing files...")

        # For QA, sync to qa_data directory
        if env_name == "qa":
            qa_dir = BASE_DIR / "qa_data"
            qa_dir.mkdir(exist_ok=True)
            # Copy necessary files (excluding databases)
            # This is handled by deploy.sh typically

        update_deployment_progress(80, "Restarting server...")

        # Restart server
        if env.get("auto_restart"):
            restart_server(env_name)

        update_deployment_progress(90, "Verifying deployment...")

        # Verify server is running
        time.sleep(3)
        ok, out, _ = run_cmd(f'curl -sk https://localhost:{env["port"]}/health')
        if "ok" not in out.lower() and "healthy" not in out.lower():
            # Try simple check
            ok, out, _ = run_cmd(f'lsof -ti:{env["port"]}')
            if not out:
                raise Exception("Server failed to start")

        # Record deployment
        deployment = {
            "environment": env_name,
            "version": version or get_current_commit(),
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
        state["deployments"].append(deployment)
        state["last_commit"][env_name] = get_current_commit()
        if version:
            state["last_tag"][env_name] = version
        save_state(state)

        update_deployment_progress(95, "Deployment complete!")
        log(f"Successfully deployed to {env_name}")

        # Deploy to cluster nodes
        cluster_nodes = get_nodes_for_environment(env_name)
        if cluster_nodes:
            log(f"Triggering cluster deployment to: {', '.join(cluster_nodes)}")
            update_deployment_progress(97, f"Deploying to cluster ({len(cluster_nodes)} nodes)...")
            deploy_to_cluster(env_name)  # Runs async by default

        update_deployment_progress(100, "Deployment complete!")

        # Clear banner after short delay
        time.sleep(5)
        clear_deployment_banner()

        return True

    except Exception as e:
        log(f"Deployment failed: {e}", "ERROR")
        set_deployment_banner(env_name, f"Deployment failed: {e}", "error")
        time.sleep(10)
        clear_deployment_banner()
        return False


def check_node_reachable(node_name, node):
    """Check if a cluster node is reachable via SSH."""
    cmd = f"ssh -o ConnectTimeout=3 {node['ssh']} 'echo ok' 2>/dev/null"
    ok, out, _ = run_cmd(cmd, timeout=10)
    return ok and "ok" in out


def get_nodes_for_environment(env_name):
    """Get list of cluster nodes that should receive deployment for this environment."""
    if not CLUSTER_DEPLOY_ENABLED:
        return []

    nodes = []
    for node_name, node in CLUSTER_NODES.items():
        if not node.get("enabled", True):
            continue
        if env_name in node.get("environments", []):
            nodes.append(node_name)
    return nodes


def deploy_to_single_node(node_name, node, env_name):
    """Deploy to a single cluster node."""
    log(f"Deploying to cluster node: {node_name} ({node['host']}:{node['port']})")

    try:
        # Check connectivity first
        if not check_node_reachable(node_name, node):
            log(f"Node {node_name} not reachable, skipping", "WARN")
            return False

        # Rsync files (exclude databases and cache)
        excludes = "--exclude '*.db' --exclude '__pycache__' --exclude '.git' --exclude 'deploy_state.json' --exclude '*.log'"
        cmd = f"rsync -avz {excludes} {BASE_DIR}/ {node['ssh']}:{node['path']}/"
        ok, _, err = run_cmd(cmd, timeout=180)
        if not ok:
            log(f"Rsync to {node_name} failed: {err}", "ERROR")
            return False

        # Restart remote server
        port = node["port"]
        restart_cmd = f"ssh {node['ssh']} 'cd {node['path']} && lsof -ti:{port} | xargs kill -9 2>/dev/null; sleep 2; USE_HTTPS=true APP_ENV={env_name} PORT={port} nohup python3 unified_app.py > ~/edu_server_{port}.log 2>&1 &'"
        ok, _, err = run_cmd(restart_cmd, timeout=60)

        # Verify server started
        time.sleep(3)
        verify_cmd = f"ssh {node['ssh']} 'lsof -ti:{port}'"
        ok, out, _ = run_cmd(verify_cmd, timeout=10)

        if out:
            log(f"Successfully deployed to {node_name} (PID: {out.strip()})")
            return True
        else:
            log(f"Server failed to start on {node_name}", "ERROR")
            return False

    except Exception as e:
        log(f"Failed to deploy to {node_name}: {e}", "ERROR")
        return False


def deploy_to_cluster(env_name, nodes=None, async_deploy=None):
    """
    Deploy to cluster nodes for the specified environment.

    Args:
        env_name: Environment being deployed ('dev', 'qa', 'prod')
        nodes: Specific nodes to deploy to (default: all nodes configured for env)
        async_deploy: Run in background thread (default: CLUSTER_DEPLOY_ASYNC)
    """
    if async_deploy is None:
        async_deploy = CLUSTER_DEPLOY_ASYNC

    # Get nodes to deploy to
    if nodes is None:
        nodes = get_nodes_for_environment(env_name)
    elif isinstance(nodes, str):
        nodes = [nodes]

    if not nodes:
        log(f"No cluster nodes configured for {env_name}")
        return

    log(f"Cluster deployment for {env_name}: {', '.join(nodes)}")

    def do_deploy():
        results = {}
        for node_name in nodes:
            node = CLUSTER_NODES.get(node_name)
            if not node:
                log(f"Unknown node: {node_name}", "WARN")
                continue

            set_deployment_banner(env_name, f"Deploying to {node_name}...", "deploying")
            results[node_name] = deploy_to_single_node(node_name, node, env_name)

        # Summary
        success = sum(1 for r in results.values() if r)
        total = len(results)
        log(f"Cluster deployment complete: {success}/{total} nodes successful")
        return results

    if async_deploy:
        thread = Thread(target=do_deploy, daemon=True)
        thread.start()
        log(f"Cluster deployment started in background for {', '.join(nodes)}")
        return thread
    else:
        return do_deploy()


def check_for_deployments():
    """Check if any deployments are needed."""
    state = load_state()

    # Fetch latest
    run_cmd("git fetch --all --tags")

    # Check dev branch for new commits
    current_dev = get_current_commit("origin/dev")
    last_dev = state["last_commit"].get("dev")

    if current_dev and current_dev != last_dev:
        log(f"New commit on dev: {current_dev[:8]}")
        deploy_to_env("dev")

    # Check for new version tags (QA deployment)
    tags = get_all_tags()
    qa_pattern = re.compile(ENVIRONMENTS["qa"]["tag_pattern"])
    latest_qa_tag = None
    for tag in tags:
        if qa_pattern.match(tag):
            latest_qa_tag = tag
            break

    if latest_qa_tag and latest_qa_tag != state["last_tag"].get("qa"):
        log(f"New QA tag: {latest_qa_tag}")
        deploy_to_env("qa", latest_qa_tag)

    # Check for release tags (PROD deployment)
    prod_pattern = re.compile(ENVIRONMENTS["prod"]["tag_pattern"])
    latest_prod_tag = None
    for tag in tags:
        if prod_pattern.match(tag):
            latest_prod_tag = tag
            break

    if latest_prod_tag and latest_prod_tag != state["last_tag"].get("prod"):
        log(f"New PROD tag: {latest_prod_tag}")
        # Prod requires manual approval
        log("Production deployment requires manual approval. Run:")
        log(f"  DEPLOY_APPROVED=1 python3 deploy_worker.py deploy prod {latest_prod_tag}")


def run_worker():
    """Run the deployment worker daemon."""
    log("Deployment worker started")
    log(f"Watching for changes every {POLL_INTERVAL} seconds")
    log(f"DEV: merge to dev -> port {ENVIRONMENTS['dev']['port']}")
    log(f"QA: tag v*.*.* -> port {ENVIRONMENTS['qa']['port']}")
    log(f"PROD: tag release-* -> port {ENVIRONMENTS['prod']['port']} (requires approval)")

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    def handle_signal(sig, frame):
        log("Worker stopped")
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while True:
        try:
            check_for_deployments()
        except Exception as e:
            log(f"Error checking deployments: {e}", "ERROR")

        time.sleep(POLL_INTERVAL)


def show_status():
    """Show deployment status."""
    state = load_state()

    print("=" * 70)
    print("DEPLOYMENT WORKER STATUS")
    print("=" * 70)

    # Current deployment
    active = state.get("active_deployment")
    if active:
        print(f"\n🚀 ACTIVE DEPLOYMENT:")
        print(f"   Environment: {active['environment']}")
        print(f"   Status: {active['status']}")
        print(f"   Progress: {active['progress']}%")
        print(f"   Message: {active['message']}")
    else:
        print("\n✓ No active deployment")

    # Environment status
    print("\nENVIRONMENTS:")
    print("-" * 70)
    for env_name, env in ENVIRONMENTS.items():
        port = env["port"]
        ok, out, _ = run_cmd(f"lsof -ti:{port}")
        running = "RUNNING" if out else "STOPPED"
        last = (
            state["last_commit"].get(env_name, "never")[:8]
            if state["last_commit"].get(env_name)
            else "never"
        )
        last_tag = state["last_tag"].get(env_name, "-")

        print(f"  {env_name.upper():<6} Port {port}  [{running}]")
        print(f"         Last commit: {last}")
        print(f"         Last tag: {last_tag}")
        print()

    # Recent deployments
    print("RECENT DEPLOYMENTS:")
    print("-" * 70)
    for dep in state.get("deployments", [])[-5:]:
        status = "✓" if dep["status"] == "success" else "✗"
        version = dep.get("version", "unknown")[:8]
        print(f"  {status} {dep['timestamp']} - {dep['environment']} - {version}")

    # Worker status
    print("\nWORKER:")
    print("-" * 70)
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        # Check if process is running
        try:
            os.kill(int(pid), 0)
            print(f"  Running (PID: {pid})")
        except:
            print(f"  Stale PID file (worker not running)")
    else:
        print("  Not running")

    # Cluster nodes
    print("\nCLUSTER NODES:")
    print("-" * 70)
    print(f"  Cluster Deploy Enabled: {CLUSTER_DEPLOY_ENABLED}")
    print(f"  Async Deploy: {CLUSTER_DEPLOY_ASYNC}")
    print()
    for node_name, node in CLUSTER_NODES.items():
        enabled = "ENABLED" if node.get("enabled", True) else "DISABLED"
        envs = ", ".join(node.get("environments", []))
        print(f"  {node_name:<12} {node['host']}:{node['port']}  [{enabled}]")
        print(f"               Environments: {envs}")
        print(f"               SSH: {node['ssh']} -> {node['path']}")
        print()

    print("=" * 70)


def main():
    if len(sys.argv) < 2:
        show_status()
        print("\nUsage:")
        print("  python3 deploy_worker.py watch            # Run worker (foreground)")
        print("  python3 deploy_worker.py start            # Start worker daemon")
        print("  python3 deploy_worker.py stop             # Stop worker daemon")
        print("  python3 deploy_worker.py deploy <env> [version]  # Deploy to environment")
        print("  python3 deploy_worker.py cluster <env> [nodes]   # Deploy to cluster nodes")
        print("  python3 deploy_worker.py nodes            # Show cluster node status")
        print("  python3 deploy_worker.py status           # Show deployment status")
        print()
        print("Environments: dev, qa, prod")
        print("Cluster nodes: " + ", ".join(CLUSTER_NODES.keys()))
        return

    cmd = sys.argv[1]

    if cmd in ["watch", "run"]:
        run_worker()

    elif cmd == "start":
        # Start as background daemon
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            try:
                os.kill(int(pid), 0)
                print(f"Worker already running (PID: {pid})")
                return
            except:
                pass

        # Fork to background
        pid = os.fork()
        if pid > 0:
            print(f"Deployment worker started (PID: {pid})")
            sys.exit(0)

        os.setsid()
        run_worker()

    elif cmd == "stop":
        if PID_FILE.exists():
            pid = PID_FILE.read_text().strip()
            try:
                os.kill(int(pid), signal.SIGTERM)
                print(f"Stopped worker (PID: {pid})")
            except:
                print("Worker not running")
            PID_FILE.unlink(missing_ok=True)
        else:
            print("Worker not running")

    elif cmd == "deploy":
        if len(sys.argv) < 3:
            print("Usage: deploy_worker.py deploy <env> [version]")
            return
        env = sys.argv[2]
        version = sys.argv[3] if len(sys.argv) > 3 else None
        deploy_to_env(env, version)

    elif cmd == "status":
        show_status()

    elif cmd == "cluster":
        # Deploy to cluster nodes
        env = sys.argv[2] if len(sys.argv) > 2 else "dev"
        nodes = sys.argv[3].split(",") if len(sys.argv) > 3 else None
        deploy_to_cluster(env, nodes, async_deploy=False)

    elif cmd == "nodes":
        # Show cluster node status with connectivity test
        print("\n" + "=" * 70)
        print("CLUSTER NODE STATUS")
        print("=" * 70)
        print(f"\nCluster Deploy: {'ENABLED' if CLUSTER_DEPLOY_ENABLED else 'DISABLED'}")
        print()

        for node_name, node in CLUSTER_NODES.items():
            print(f"  {node_name}")
            print(f"    Host: {node['host']}:{node['port']}")
            print(f"    SSH: {node['ssh']} -> {node['path']}")
            print(f"    Environments: {', '.join(node.get('environments', []))}")
            print(f"    Config: {'ENABLED' if node.get('enabled', True) else 'DISABLED'}")

            # Test connectivity
            if node.get("enabled", True):
                reachable = check_node_reachable(node_name, node)
                status = "✓ REACHABLE" if reachable else "✗ NOT REACHABLE"
                print(f"    Status: {status}")

                if reachable:
                    # Check if server is running
                    verify_cmd = f"ssh -o ConnectTimeout=5 {node['ssh']} 'lsof -ti:{node['port']}'"
                    ok, out, _ = run_cmd(verify_cmd, timeout=30)
                    if out:
                        print(f"    Server: RUNNING (PID: {out.strip()})")
                    else:
                        print(f"    Server: STOPPED")
            else:
                print(f"    Status: DISABLED")

            print()
        print("=" * 70)

    elif cmd == "enable-node":
        # Enable/disable cluster node
        if len(sys.argv) < 3:
            print("Usage: deploy_worker.py enable-node <node_name>")
            return
        node_name = sys.argv[2]
        if node_name in CLUSTER_NODES:
            print(f"Node {node_name} configuration is in the script.")
            print("Edit CLUSTER_NODES['enabled'] in deploy_worker.py to change.")
        else:
            print(f"Unknown node: {node_name}")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
