#!/usr/bin/env python3
"""
HAR File Analyzer for QA
Parses HTTP Archive (HAR) files and analyzes for errors, performance issues, and security concerns.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class HARAnalyzer:
    """Analyzes HAR files for errors and issues"""

    def __init__(self, har_file: str):
        self.har_file = Path(har_file)
        self.data = self._load_har()
        self.issues = []
        self.warnings = []
        self.info = []

    def _load_har(self) -> Dict:
        """Load and parse HAR file"""
        try:
            with open(self.har_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load HAR file: {e}")
            sys.exit(1)

    def analyze(self) -> Dict[str, Any]:
        """Run all analysis checks"""
        print(f"\n🔍 Analyzing HAR file: {self.har_file.name}")
        print("=" * 60)

        self._check_http_errors()
        self._check_slow_requests()
        self._check_security_issues()
        self._check_console_errors()
        self._check_resource_sizes()
        self._analyze_performance()

        return self._generate_report()

    def _check_http_errors(self):
        """Check for HTTP error status codes"""
        entries = self.data.get("log", {}).get("entries", [])

        errors_4xx = []
        errors_5xx = []

        for entry in entries:
            status = entry.get("response", {}).get("status", 0)
            url = entry.get("request", {}).get("url", "unknown")

            if 400 <= status < 500:
                errors_4xx.append({"status": status, "url": url})
            elif 500 <= status < 600:
                errors_5xx.append({"status": status, "url": url})

        if errors_5xx:
            self.issues.append(
                {
                    "type": "HTTP 5xx Errors",
                    "severity": "critical",
                    "count": len(errors_5xx),
                    "details": errors_5xx[:5],  # Show first 5
                }
            )

        if errors_4xx:
            self.warnings.append(
                {
                    "type": "HTTP 4xx Errors",
                    "severity": "warning",
                    "count": len(errors_4xx),
                    "details": errors_4xx[:5],  # Show first 5
                }
            )

    def _check_slow_requests(self):
        """Check for slow HTTP requests"""
        entries = self.data.get("log", {}).get("entries", [])
        slow_threshold_ms = 3000  # 3 seconds
        very_slow_threshold_ms = 10000  # 10 seconds

        slow_requests = []
        very_slow_requests = []

        for entry in entries:
            time_ms = entry.get("time", 0)
            url = entry.get("request", {}).get("url", "unknown")

            if time_ms > very_slow_threshold_ms:
                very_slow_requests.append({"time": f"{time_ms}ms", "url": url})
            elif time_ms > slow_threshold_ms:
                slow_requests.append({"time": f"{time_ms}ms", "url": url})

        if very_slow_requests:
            self.issues.append(
                {
                    "type": "Very Slow Requests (>10s)",
                    "severity": "high",
                    "count": len(very_slow_requests),
                    "details": very_slow_requests[:5],
                }
            )

        if slow_requests:
            self.warnings.append(
                {
                    "type": "Slow Requests (>3s)",
                    "severity": "medium",
                    "count": len(slow_requests),
                    "details": slow_requests[:5],
                }
            )

    def _check_security_issues(self):
        """Check for security-related issues"""
        entries = self.data.get("log", {}).get("entries", [])

        insecure_resources = []
        missing_security_headers = []

        for entry in entries:
            url = entry.get("request", {}).get("url", "")
            headers = {
                h["name"].lower(): h["value"] for h in entry.get("response", {}).get("headers", [])
            }

            # Check for HTTP resources on HTTPS pages
            if url.startswith("http://") and not url.startswith("http://localhost"):
                insecure_resources.append(url)

            # Check for missing security headers on HTML responses
            content_type = headers.get("content-type", "")
            if "text/html" in content_type:
                if "x-content-type-options" not in headers:
                    missing_security_headers.append(
                        {"url": url, "missing": "X-Content-Type-Options"}
                    )
                if "x-frame-options" not in headers and "content-security-policy" not in headers:
                    missing_security_headers.append(
                        {"url": url, "missing": "X-Frame-Options / CSP"}
                    )

        if insecure_resources:
            self.warnings.append(
                {
                    "type": "Insecure Resources (HTTP)",
                    "severity": "medium",
                    "count": len(insecure_resources),
                    "details": insecure_resources[:5],
                }
            )

        if missing_security_headers:
            self.info.append(
                {
                    "type": "Missing Security Headers",
                    "severity": "low",
                    "count": len(missing_security_headers),
                    "details": missing_security_headers[:5],
                }
            )

    def _check_console_errors(self):
        """Check for JavaScript console errors"""
        # HAR files don't always capture console errors, but we can check response bodies
        # for common error patterns if available
        pass

    def _check_resource_sizes(self):
        """Check for large resource sizes"""
        entries = self.data.get("log", {}).get("entries", [])
        large_threshold = 1024 * 1024  # 1MB

        large_resources = []

        for entry in entries:
            size = entry.get("response", {}).get("bodySize", 0)
            url = entry.get("request", {}).get("url", "unknown")

            if size > large_threshold:
                large_resources.append({"size": f"{size / 1024 / 1024:.2f}MB", "url": url})

        if large_resources:
            self.info.append(
                {
                    "type": "Large Resources (>1MB)",
                    "severity": "low",
                    "count": len(large_resources),
                    "details": large_resources[:5],
                }
            )

    def _analyze_performance(self):
        """Analyze overall performance metrics"""
        entries = self.data.get("log", {}).get("entries", [])

        if not entries:
            return

        total_size = sum(e.get("response", {}).get("bodySize", 0) for e in entries)
        total_time = sum(e.get("time", 0) for e in entries)
        total_requests = len(entries)

        self.info.append(
            {
                "type": "Performance Summary",
                "severity": "info",
                "details": {
                    "total_requests": total_requests,
                    "total_size": f"{total_size / 1024 / 1024:.2f}MB",
                    "total_time": f"{total_time / 1000:.2f}s",
                    "avg_time_per_request": (
                        f"{total_time / total_requests if total_requests > 0 else 0:.0f}ms"
                    ),
                },
            }
        )

    def _generate_report(self) -> Dict[str, Any]:
        """Generate analysis report"""
        print("\n" + "=" * 60)
        print("📊 ANALYSIS REPORT")
        print("=" * 60)

        # Print issues
        if self.issues:
            print(f"\n🔴 CRITICAL ISSUES ({len(self.issues)}):")
            for issue in self.issues:
                print(f"\n  {issue['type']} (Count: {issue.get('count', 0)})")
                if "details" in issue:
                    for detail in issue["details"]:
                        if isinstance(detail, dict):
                            print(f"    - {detail}")
                        else:
                            print(f"    - {detail}")
        else:
            print("\n✅ No critical issues found")

        # Print warnings
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"\n  {warning['type']} (Count: {warning.get('count', 0)})")
                if "details" in warning:
                    for detail in warning["details"][:3]:  # Show first 3
                        if isinstance(detail, dict):
                            print(f"    - {detail}")
                        else:
                            print(f"    - {detail}")
        else:
            print("\n✅ No warnings")

        # Print info
        if self.info:
            print(f"\n💡 INFO ({len(self.info)}):")
            for info in self.info:
                print(f"\n  {info['type']}")
                if isinstance(info.get("details"), dict):
                    for key, value in info["details"].items():
                        print(f"    {key}: {value}")
                elif "details" in info:
                    for detail in info["details"][:3]:
                        if isinstance(detail, dict):
                            print(f"    - {detail}")
                        else:
                            print(f"    - {detail}")

        print("\n" + "=" * 60)

        # Determine overall status
        if self.issues:
            status = "FAILED"
            print(f"❌ Status: {status} - Critical issues found")
        elif self.warnings:
            status = "WARNING"
            print(f"⚠️  Status: {status} - Warnings present")
        else:
            status = "PASSED"
            print(f"✅ Status: {status} - All checks passed")

        print("=" * 60 + "\n")

        return {
            "status": status,
            "har_file": str(self.har_file),
            "timestamp": datetime.now().isoformat(),
            "issues": self.issues,
            "warnings": self.warnings,
            "info": self.info,
        }


def main():
    parser = argparse.ArgumentParser(description="Analyze HAR files for errors and issues")
    parser.add_argument("har_file", help="Path to HAR file to analyze")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--output", help="Save report to file")

    args = parser.parse_args()

    # Analyze HAR file
    analyzer = HARAnalyzer(args.har_file)
    report = analyzer.analyze()

    # Save report if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {args.output}")

    # Output JSON if requested
    if args.json:
        print(json.dumps(report, indent=2))

    # Exit with error code if issues found
    if report["status"] == "FAILED":
        sys.exit(1)
    elif report["status"] == "WARNING":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
