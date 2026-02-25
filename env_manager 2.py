#!/usr/bin/env python3
"""
Environment Manager - Central control for all architect environments

Usage:
    ./env_manager.py list                    # List all environments
    ./env_manager.py status                  # Show running status
    ./env_manager.py start <env>             # Start an environment
    ./env_manager.py stop <env>              # Stop an environment
    ./env_manager.py restart <env>           # Restart an environment
    ./env_manager.py start-all               # Start all auto_start environments
    ./env_manager.py stop-all                # Stop all environments
    ./env_manager.py create <name> <port>    # Create new feature environment
    ./env_manager.py logs <env>              # Tail logs for environment
"""

import json
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "data" / "environments.json"
DB_PATH = BASE_DIR / "data" / "task_delegator.db"

# ANSI colors
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"


def load_config():
    """Load environment configuration"""
    if not CONFIG_PATH.exists():
        print(f"{RED}Config not found: {CONFIG_PATH}{RESET}")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config):
    """Save environment configuration"""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_pid_on_port(port):
    """Get PID of process listening on port"""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except:
        pass
    return None


def is_running(port):
    """Check if environment is running on port"""
    return get_pid_on_port(port) is not None


def start_env(env_name, config):
    """Start an environment"""
    envs = config.get("architect_envs", {})
    defaults = config.get("defaults", {})

    if env_name not in envs:
        print(f"{RED}Unknown environment: {env_name}{RESET}")
        print(f"Available: {', '.join(envs.keys())}")
        return False

    env = envs[env_name]
    port = env["port"]

    if is_running(port):
        print(f"{YELLOW}{env_name} already running on port {port}{RESET}")
        return True

    python = defaults.get("python", "python3")
    app = defaults.get("architect_app", "app.py")
    log_dir = defaults.get("log_dir", "/tmp")
    log_file = f"{log_dir}/architect_{env_name}.log"

    # Start the server
    cmd = f"APP_ENV={env_name} PORT={port} {python} {app} --ssl >> {log_file} 2>&1 &"

    os.chdir(BASE_DIR)
    subprocess.run(cmd, shell=True)

    # Wait and verify
    import time

    time.sleep(2)

    if is_running(port):
        print(f"{GREEN}✓ Started {env_name} on https://0.0.0.0:{port}{RESET}")
        print(f"  Database: data/{env_name}/architect.db")
        print(f"  Log: {log_file}")
        return True
    else:
        print(f"{RED}✗ Failed to start {env_name}{RESET}")
        print(f"  Check log: {log_file}")
        return False


def stop_env(env_name, config):
    """Stop an environment"""
    envs = config.get("architect_envs", {})

    if env_name not in envs:
        print(f"{RED}Unknown environment: {env_name}{RESET}")
        return False

    port = envs[env_name]["port"]
    pid = get_pid_on_port(port)

    if not pid:
        print(f"{DIM}{env_name} not running{RESET}")
        return True

    try:
        os.kill(pid, signal.SIGTERM)
        import time

        time.sleep(1)

        # Force kill if still running
        if is_running(port):
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)

        print(f"{GREEN}✓ Stopped {env_name} (was on port {port}){RESET}")
        return True
    except Exception as e:
        print(f"{RED}✗ Failed to stop {env_name}: {e}{RESET}")
        return False


def list_envs(config):
    """List all environments"""
    envs = config.get("architect_envs", {})

    print(f"\n{BOLD}=== ARCHITECT ENVIRONMENTS ==={RESET}")
    print(f"{'NAME':<12} {'PORT':<6} {'TYPE':<10} {'AUTO':<6} DESCRIPTION")
    print("-" * 60)

    for name, env in envs.items():
        auto = "yes" if env.get("auto_start") else "no"
        print(
            f"{name:<12} {env['port']:<6} {env['type']:<10} {auto:<6} {env.get('description', '')}"
        )

    # Also show edu app envs
    edu_envs = config.get("edu_app_envs", {})
    if edu_envs:
        print(f"\n{BOLD}=== EDU APP ENVIRONMENTS ==={RESET}")
        print(f"{'NAME':<12} {'TYPE':<10} PATH")
        print("-" * 60)
        for name, env in edu_envs.items():
            print(f"{name:<12} {env['type']:<10} {env['path']}")


def status(config):
    """Show running status of all environments"""
    envs = config.get("architect_envs", {})

    print(f"\n{BOLD}=== ENVIRONMENT STATUS ==={RESET}")
    print(f"{'NAME':<12} {'PORT':<6} {'STATUS':<12} {'PID':<8} URL")
    print("-" * 70)

    for name, env in envs.items():
        port = env["port"]
        pid = get_pid_on_port(port)

        if pid:
            status_str = f"{GREEN}RUNNING{RESET}"
            url = f"https://0.0.0.0:{port}"
        else:
            status_str = f"{DIM}stopped{RESET}"
            pid = "-"
            url = "-"

        print(f"{name:<12} {port:<6} {status_str:<21} {str(pid):<8} {url}")


def create_env(name, port, config):
    """Create a new feature environment"""
    envs = config.get("architect_envs", {})

    if name in envs:
        print(f"{RED}Environment '{name}' already exists{RESET}")
        return False

    # Check port not in use
    for existing_name, env in envs.items():
        if env["port"] == port:
            print(f"{RED}Port {port} already used by '{existing_name}'{RESET}")
            return False

    # Create data directory
    data_dir = BASE_DIR / "data" / name
    data_dir.mkdir(parents=True, exist_ok=True)

    # Add to config
    envs[name] = {
        "port": port,
        "type": "feature",
        "description": f"Feature environment {name}",
        "auto_start": False,
    }

    save_config(config)

    print(f"{GREEN}✓ Created environment '{name}' on port {port}{RESET}")
    print(f"  Data dir: {data_dir}")
    print(f"  Start with: ./env_manager.py start {name}")
    return True


def tail_logs(env_name, config):
    """Tail logs for an environment"""
    defaults = config.get("defaults", {})
    log_dir = defaults.get("log_dir", "/tmp")
    log_file = f"{log_dir}/architect_{env_name}.log"

    if not os.path.exists(log_file):
        print(f"{RED}Log file not found: {log_file}{RESET}")
        return

    print(f"{DIM}Tailing {log_file} (Ctrl+C to stop){RESET}\n")
    subprocess.run(["tail", "-f", log_file])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    config = load_config()

    if cmd == "list":
        list_envs(config)

    elif cmd == "status":
        status(config)

    elif cmd == "start" and len(sys.argv) >= 3:
        start_env(sys.argv[2], config)

    elif cmd == "stop" and len(sys.argv) >= 3:
        stop_env(sys.argv[2], config)

    elif cmd == "restart" and len(sys.argv) >= 3:
        env_name = sys.argv[2]
        stop_env(env_name, config)
        import time

        time.sleep(1)
        start_env(env_name, config)

    elif cmd == "start-all":
        envs = config.get("architect_envs", {})
        for name, env in envs.items():
            if env.get("auto_start"):
                start_env(name, config)

    elif cmd == "stop-all":
        envs = config.get("architect_envs", {})
        for name in envs:
            stop_env(name, config)

    elif cmd == "create" and len(sys.argv) >= 4:
        name = sys.argv[2]
        port = int(sys.argv[3])
        create_env(name, port, config)

    elif cmd == "logs" and len(sys.argv) >= 3:
        tail_logs(sys.argv[2], config)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
