#!/usr/bin/env python3
"""
Supervisor Control CLI

Command-line interface for managing supervised services:
- Start/stop/restart services
- Check status
- View logs
- Monitor health
- Configure services
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from supervisor.supervisor_integration import SupervisorIntegration

    INTEGRATION_AVAILABLE = True
except ImportError:
    INTEGRATION_AVAILABLE = False


class SupervisorCtl:
    """Supervisor control interface."""

    def __init__(self, dashboard_url: str = "http://localhost:8080"):
        """Initialize controller.

        Args:
            dashboard_url: Dashboard URL for API calls
        """
        self.dashboard_url = dashboard_url
        self.integration = SupervisorIntegration() if INTEGRATION_AVAILABLE else None

    def status(self, service_id: Optional[str] = None):
        """Show service status.

        Args:
            service_id: Optional service ID to filter
        """
        if self.integration:
            services = self.integration.get_service_status(service_id)
        else:
            # Fallback to API call
            try:
                response = requests.get(f"{self.dashboard_url}/api/supervisor/status")
                services = response.json().get("services", [])
                if service_id:
                    services = [s for s in services if s["id"] == service_id]
            except Exception as e:
                print(f"❌ Error: {e}")
                return

        if not services:
            print("No services found" if not service_id else f"Service '{service_id}' not found")
            return

        # Print header
        print("\n" + "━" * 100)
        print("📊 Supervisor Status")
        print("━" * 100)
        print(
            f"\n{'Service':<20} {'State':<12} {'PID':<8} {'Port':<6} {'Uptime':<12} {'Restarts':<10} {'Critical':<10}"
        )
        print("-" * 100)

        # Print services
        for service in services:
            state_icon = {
                "running": "✅",
                "stopped": "⏸️ ",
                "starting": "🔄",
                "stopping": "⏹️ ",
                "failed": "❌",
                "backoff": "⏳",
                "fatal": "💀",
            }.get(service.get("state", "unknown"), "❓")

            uptime = self._format_uptime(service.get("uptime_seconds", 0))
            critical = "✓" if service.get("critical") else ""

            print(
                f"{service['id']:<20} "
                f"{state_icon} {service.get('state', 'unknown'):<10} "
                f"{service.get('pid', '-'):<8} "
                f"{service.get('port', '-'):<6} "
                f"{uptime:<12} "
                f"{service.get('restart_count', 0):<10} "
                f"{critical:<10}"
            )

        print()

    def start(self, service_id: str):
        """Start a service.

        Args:
            service_id: Service ID to start
        """
        print(f"🚀 Starting service '{service_id}'...")

        try:
            response = requests.post(
                f"{self.dashboard_url}/api/supervisor/services/{service_id}/start"
            )

            if response.status_code == 200:
                print(f"✅ Service '{service_id}' started")
            else:
                print(f"❌ Failed to start: {response.text}")

        except Exception as e:
            print(f"❌ Error: {e}")

    def stop(self, service_id: str):
        """Stop a service.

        Args:
            service_id: Service ID to stop
        """
        print(f"⏹️  Stopping service '{service_id}'...")

        try:
            response = requests.post(
                f"{self.dashboard_url}/api/supervisor/services/{service_id}/stop"
            )

            if response.status_code == 200:
                print(f"✅ Service '{service_id}' stopped")
            else:
                print(f"❌ Failed to stop: {response.text}")

        except Exception as e:
            print(f"❌ Error: {e}")

    def restart(self, service_id: str):
        """Restart a service.

        Args:
            service_id: Service ID to restart
        """
        print(f"🔄 Restarting service '{service_id}'...")

        try:
            response = requests.post(
                f"{self.dashboard_url}/api/supervisor/services/{service_id}/restart"
            )

            if response.status_code == 200:
                print(f"✅ Service '{service_id}' restarted")
            else:
                print(f"❌ Failed to restart: {response.text}")

        except Exception as e:
            print(f"❌ Error: {e}")

    def logs(self, service_id: str, lines: int = 50, follow: bool = False):
        """Show service logs.

        Args:
            service_id: Service ID
            lines: Number of lines to show
            follow: Follow log output
        """
        log_file = Path(f"/tmp/supervisor_logs/{service_id}.log")

        if not log_file.exists():
            print(f"❌ Log file not found: {log_file}")
            return

        if follow:
            # Use tail -f
            subprocess.run(["tail", "-f", "-n", str(lines), str(log_file)])
        else:
            # Show last N lines
            subprocess.run(["tail", "-n", str(lines), str(log_file)])

    def health(self, service_id: Optional[str] = None):
        """Show health status.

        Args:
            service_id: Optional service ID to filter
        """
        try:
            if service_id:
                response = requests.get(
                    f"{self.dashboard_url}/api/supervisor/services/{service_id}/health"
                )
            else:
                response = requests.get(f"{self.dashboard_url}/api/supervisor/health")

            if response.status_code == 200:
                data = response.json()
                print(json.dumps(data, indent=2))
            else:
                print(f"❌ Failed to get health status: {response.text}")

        except Exception as e:
            print(f"❌ Error: {e}")

    def events(self, service_id: Optional[str] = None, limit: int = 20):
        """Show recent events.

        Args:
            service_id: Optional service ID to filter
            limit: Maximum number of events to show
        """
        if self.integration:
            events = self.integration.get_service_events(service_id, limit=limit)
        else:
            # Fallback to API call
            try:
                params = {"limit": limit}
                if service_id:
                    params["service_id"] = service_id

                response = requests.get(
                    f"{self.dashboard_url}/api/supervisor/events", params=params
                )
                events = response.json().get("events", [])
            except Exception as e:
                print(f"❌ Error: {e}")
                return

        if not events:
            print("No events found")
            return

        print("\n" + "━" * 100)
        print("📋 Recent Events")
        print("━" * 100)
        print(f"\n{'Timestamp':<20} {'Service':<20} {'Event':<15} {'Message':<45}")
        print("-" * 100)

        for event in events:
            timestamp = event["timestamp"][:19] if "timestamp" in event else "N/A"
            print(
                f"{timestamp:<20} "
                f"{event.get('service_id', 'unknown'):<20} "
                f"{event.get('event_type', 'unknown'):<15} "
                f"{event.get('message', '')[:45]:<45}"
            )

        print()

    def reload_config(self):
        """Reload supervisor configuration."""
        print("🔄 Reloading supervisor configuration...")

        try:
            response = requests.post(f"{self.dashboard_url}/api/supervisor/reload")

            if response.status_code == 200:
                print("✅ Configuration reloaded")
            else:
                print(f"❌ Failed to reload: {response.text}")

        except Exception as e:
            print(f"❌ Error: {e}")

    def summary(self):
        """Show dashboard summary."""
        if self.integration:
            summary = self.integration.get_dashboard_summary()
        else:
            try:
                response = requests.get(f"{self.dashboard_url}/api/supervisor/summary")
                summary = response.json()
            except Exception as e:
                print(f"❌ Error: {e}")
                return

        print("\n" + "━" * 60)
        print("📊 Supervisor Summary")
        print("━" * 60)

        # State counts
        state_counts = summary.get("state_counts", {})
        print(f"\nService States:")
        for state, count in state_counts.items():
            icon = {
                "running": "✅",
                "stopped": "⏸️ ",
                "failed": "❌",
                "backoff": "⏳",
                "fatal": "💀",
            }.get(state, "❓")
            print(f"  {icon} {state.capitalize():<12}: {count}")

        # Critical services
        critical = summary.get("critical_services", [])
        if critical:
            print(f"\nCritical Services: {len(critical)}")
            for service in critical:
                state_icon = {"running": "✅", "stopped": "⏸️ ", "failed": "❌"}.get(
                    service.get("state"), "❓"
                )
                print(f"  {state_icon} {service['id']:<20} - {service.get('name', 'N/A')}")

        # Recent failures
        failures = summary.get("recent_failures", [])
        if failures:
            print(f"\nRecent Failures (last hour):")
            for failure in failures:
                print(f"  ⚠️  {failure['service_id']:<20} - {failure['failure_count']} failures")

        print(f"\nTotal Services: {summary.get('total_services', 0)}")
        print()

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human-readable format."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
        else:
            return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Supervisor Control CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                    Show all services
  %(prog)s status architect-prod     Show specific service
  %(prog)s start architect-prod      Start service
  %(prog)s restart reading-app       Restart service
  %(prog)s logs architect-prod       Show logs
  %(prog)s logs architect-prod -f    Follow logs
  %(prog)s health                    Show health status
  %(prog)s events                    Show recent events
  %(prog)s summary                   Show summary
        """,
    )

    parser.add_argument(
        "--dashboard", type=str, default="http://localhost:8080", help="Dashboard URL"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show service status")
    status_parser.add_argument("service", nargs="?", help="Service ID")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start service")
    start_parser.add_argument("service", help="Service ID")

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop service")
    stop_parser.add_argument("service", help="Service ID")

    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart service")
    restart_parser.add_argument("service", help="Service ID")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show service logs")
    logs_parser.add_argument("service", help="Service ID")
    logs_parser.add_argument("-n", "--lines", type=int, default=50, help="Number of lines to show")
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output")

    # Health command
    health_parser = subparsers.add_parser("health", help="Show health status")
    health_parser.add_argument("service", nargs="?", help="Service ID")

    # Events command
    events_parser = subparsers.add_parser("events", help="Show recent events")
    events_parser.add_argument("service", nargs="?", help="Service ID")
    events_parser.add_argument(
        "-n", "--limit", type=int, default=20, help="Maximum number of events"
    )

    # Reload command
    subparsers.add_parser("reload", help="Reload configuration")

    # Summary command
    subparsers.add_parser("summary", help="Show summary")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    ctl = SupervisorCtl(dashboard_url=args.dashboard)

    try:
        if args.command == "status":
            ctl.status(args.service if hasattr(args, "service") else None)
        elif args.command == "start":
            ctl.start(args.service)
        elif args.command == "stop":
            ctl.stop(args.service)
        elif args.command == "restart":
            ctl.restart(args.service)
        elif args.command == "logs":
            ctl.logs(args.service, lines=args.lines, follow=args.follow)
        elif args.command == "health":
            ctl.health(args.service if hasattr(args, "service") else None)
        elif args.command == "events":
            ctl.events(args.service if hasattr(args, "service") else None, limit=args.limit)
        elif args.command == "reload":
            ctl.reload_config()
        elif args.command == "summary":
            ctl.summary()

    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
