#!/usr/bin/env python3
"""
Site Health Monitor Worker
Continuously checks critical sites and auto-dispatches fix requests to Claude instances
"""

import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

# Critical sites to monitor
MONITORED_SITES = [
    {
        "url": "http://100.112.58.92:8081/monitor.html",
        "name": "Task Monitor Dashboard",
        "check_interval": 60,  # seconds
        "timeout": 10,
        "expected_status": 200,
    },
    {
        "url": "https://192.168.1.231:5063/reading/",
        "name": "Reading App (Eden)",
        "check_interval": 120,
        "timeout": 10,
        "expected_status": 200,
        "verify_ssl": False,
    },
    {
        "url": "https://100.112.58.92:8080/",
        "name": "Architect Dashboard",
        "check_interval": 60,
        "timeout": 10,
        "expected_status": 200,
        "verify_ssl": False,
    },
    {
        "url": "http://100.112.58.92:7085/",
        "name": "Selam Pharmacy",
        "check_interval": 120,
        "timeout": 10,
        "expected_status": 200,
    },
]

# Claude instance for recurring server issues
DEVOPS_CLAUDE_SESSION = "arch_worker1"


class SiteHealthMonitor:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.db_path = self.base_dir / "data" / "site_health.db"
        self.init_database()

    def init_database(self):
        """Initialize health check database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_name TEXT NOT NULL,
                url TEXT NOT NULL,
                status_code INTEGER,
                response_time_ms INTEGER,
                is_healthy BOOLEAN,
                error_message TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS outages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_name TEXT NOT NULL,
                url TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                duration_seconds INTEGER,
                fix_request_sent BOOLEAN DEFAULT 0,
                fix_prompt_id INTEGER,
                resolved BOOLEAN DEFAULT 0
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_health_checks_site
            ON health_checks(site_name, checked_at DESC)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_outages_active
            ON outages(site_name, resolved)
        """
        )

        conn.commit()
        conn.close()

    def check_site(self, site_config):
        """Check if a site is healthy"""
        url = site_config["url"]
        name = site_config["name"]
        timeout = site_config["timeout"]
        expected_status = site_config["expected_status"]
        verify_ssl = site_config.get("verify_ssl", True)

        start_time = time.time()

        try:
            response = requests.get(url, timeout=timeout, verify=verify_ssl, allow_redirects=True)

            response_time_ms = int((time.time() - start_time) * 1000)
            is_healthy = response.status_code == expected_status

            return {
                "name": name,
                "url": url,
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
                "is_healthy": is_healthy,
                "error_message": None
                if is_healthy
                else f"Expected {expected_status}, got {response.status_code}",
            }

        except requests.exceptions.Timeout:
            response_time_ms = int((time.time() - start_time) * 1000)
            return {
                "name": name,
                "url": url,
                "status_code": None,
                "response_time_ms": response_time_ms,
                "is_healthy": False,
                "error_message": f"Timeout after {timeout}s",
            }

        except requests.exceptions.ConnectionError as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            return {
                "name": name,
                "url": url,
                "status_code": None,
                "response_time_ms": response_time_ms,
                "is_healthy": False,
                "error_message": f"Connection failed: {str(e)[:100]}",
            }

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            return {
                "name": name,
                "url": url,
                "status_code": None,
                "response_time_ms": response_time_ms,
                "is_healthy": False,
                "error_message": f"Error: {str(e)[:100]}",
            }

    def log_health_check(self, result):
        """Log health check result to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO health_checks (
                site_name, url, status_code, response_time_ms,
                is_healthy, error_message
            ) VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                result["name"],
                result["url"],
                result["status_code"],
                result["response_time_ms"],
                result["is_healthy"],
                result["error_message"],
            ),
        )

        conn.commit()
        conn.close()

    def get_active_outage(self, site_name):
        """Check if there's an active outage for this site"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, started_at, fix_request_sent, fix_prompt_id
            FROM outages
            WHERE site_name = ? AND resolved = 0
            ORDER BY started_at DESC
            LIMIT 1
        """,
            (site_name,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "started_at": row[1],
                "fix_request_sent": bool(row[2]),
                "fix_prompt_id": row[3],
            }
        return None

    def start_outage(self, site_name, url):
        """Record a new outage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO outages (site_name, url)
            VALUES (?, ?)
        """,
            (site_name, url),
        )

        outage_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return outage_id

    def end_outage(self, outage_id):
        """Mark an outage as resolved"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE outages
            SET ended_at = CURRENT_TIMESTAMP,
                duration_seconds = CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER),
                resolved = 1
            WHERE id = ?
        """,
            (outage_id,),
        )

        conn.commit()
        conn.close()

    def send_fix_request(self, site_name, url, error_message, outage_id):
        """Send fix request to Claude instance via assigner"""
        prompt = f"""🚨 URGENT: Site Down - Auto-Detected

**Site**: {site_name}
**URL**: {url}
**Error**: {error_message}
**Detected**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Required Actions**:
1. Check if the service is running (lsof -i, ps aux)
2. Check for process crashes or errors in logs
3. Identify the root cause (port conflict, crashed process, config error)
4. Restart the service if needed
5. Verify the site is back up
6. Report findings

**Auto-Dispatch**: Site health monitor detected failure and dispatched this request.
"""

        try:
            # Queue to assigner worker
            result = subprocess.run(
                [
                    "python3",
                    str(self.base_dir / "workers" / "assigner_worker.py"),
                    "--send",
                    prompt,
                    "--target",
                    DEVOPS_CLAUDE_SESSION,
                    "--priority",
                    "10",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Extract prompt ID from output
                output = result.stdout
                if "prompt" in output.lower():
                    import re

                    match = re.search(r"prompt (\d+)", output, re.IGNORECASE)
                    if match:
                        prompt_id = int(match.group(1))

                        # Update outage record
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE outages
                            SET fix_request_sent = 1, fix_prompt_id = ?
                            WHERE id = ?
                        """,
                            (prompt_id, outage_id),
                        )
                        conn.commit()
                        conn.close()

                        print(f"✅ Fix request sent: Prompt #{prompt_id} → {DEVOPS_CLAUDE_SESSION}")
                        return prompt_id

            print(f"⚠️  Fix request failed: {result.stderr}")
            return None

        except Exception as e:
            print(f"❌ Error sending fix request: {e}")
            return None

    def monitor_loop(self):
        """Main monitoring loop"""
        print(f"🔍 Site Health Monitor Started")
        print(f"   Monitoring {len(MONITORED_SITES)} sites")
        print(f"   DevOps Claude: {DEVOPS_CLAUDE_SESSION}")
        print()

        site_last_check = {site["name"]: 0 for site in MONITORED_SITES}

        while True:
            try:
                current_time = time.time()

                for site_config in MONITORED_SITES:
                    site_name = site_config["name"]
                    check_interval = site_config["check_interval"]

                    # Check if it's time to check this site
                    if current_time - site_last_check[site_name] >= check_interval:
                        # Perform health check
                        result = self.check_site(site_config)
                        self.log_health_check(result)
                        site_last_check[site_name] = current_time

                        # Get active outage if exists
                        active_outage = self.get_active_outage(site_name)

                        if result["is_healthy"]:
                            # Site is healthy
                            if active_outage:
                                # Outage resolved!
                                self.end_outage(active_outage["id"])
                                print(f"✅ {site_name} - BACK UP (was down)")
                            else:
                                print(f"✅ {site_name} - OK ({result['response_time_ms']}ms)")
                        else:
                            # Site is down
                            if active_outage:
                                # Existing outage, check if fix request sent
                                if not active_outage["fix_request_sent"]:
                                    print(f"🚨 {site_name} - STILL DOWN, sending fix request...")
                                    self.send_fix_request(
                                        site_name,
                                        result["url"],
                                        result["error_message"],
                                        active_outage["id"],
                                    )
                                else:
                                    print(
                                        f"⏳ {site_name} - DOWN (fix request sent: #{active_outage['fix_prompt_id']})"
                                    )
                            else:
                                # New outage
                                outage_id = self.start_outage(site_name, result["url"])
                                print(f"🚨 {site_name} - DOWN: {result['error_message']}")
                                print(f"   Sending fix request to {DEVOPS_CLAUDE_SESSION}...")
                                self.send_fix_request(
                                    site_name, result["url"], result["error_message"], outage_id
                                )

                # Sleep for a bit before next check cycle
                time.sleep(10)

            except KeyboardInterrupt:
                print("\n\n🛑 Monitoring stopped by user")
                break
            except Exception as e:
                print(f"❌ Monitor error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    monitor = SiteHealthMonitor()
    monitor.monitor_loop()
