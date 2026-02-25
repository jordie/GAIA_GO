#!/usr/bin/env python3
"""
Web Dashboard Server - Real-time system status on localhost:8080

Features:
- Auto-refresh every 5 seconds
- Clean, modern UI
- All status data from status_dashboard.py
- Accessible from any browser

Usage:
    python3 web_dashboard.py
    Then open: http://localhost:8080
"""
import json
import os

# Import session monitor
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS

from auto_confirm_monitor import AutoConfirmMonitor
from claude_auto_integration import ClaudeIntegration
from comet_auto_integration import CometIntegration
from perplexity_scraper import PerplexityScraper
from quality_scorer import QualityScorer
from result_comparator import ResultComparator
from smart_task_router import SmartTaskRouter
from status_dashboard import StatusDashboard

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
try:
    from foundation_session_monitor import FoundationSessionMonitor

    MONITOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Foundation session monitor not available: {e}")
    MONITOR_AVAILABLE = False

app = Flask(__name__)
CORS(app)

dashboard = StatusDashboard()
router = SmartTaskRouter()
ac_monitor = AutoConfirmMonitor()
scorer = QualityScorer()
scraper = PerplexityScraper()
claude = ClaudeIntegration()
comet = CometIntegration()
comparator = ResultComparator()

# Initialize session monitor if available
if MONITOR_AVAILABLE:
    try:
        session_monitor = FoundationSessionMonitor()
    except Exception as e:
        print(f"Warning: Could not initialize session monitor: {e}")
        session_monitor = None
else:
    session_monitor = None

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>System Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .last-updated {
            font-size: 0.9em;
            opacity: 0.9;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }

        .card:hover {
            transform: translateY(-5px);
        }

        .card-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }

        .card-icon {
            font-size: 2em;
            margin-right: 15px;
        }

        .card-title {
            font-size: 1.3em;
            font-weight: 600;
            color: #333;
        }

        .status-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            margin-left: auto;
        }

        .status-running {
            background: #d4edda;
            color: #155724;
        }

        .status-stopped {
            background: #f8d7da;
            color: #721c24;
        }

        .status-complete {
            background: #d1ecf1;
            color: #0c5460;
        }

        .metric {
            margin-bottom: 15px;
        }

        .metric-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }

        .metric-value {
            font-size: 1.5em;
            font-weight: 600;
            color: #333;
        }

        .list-item {
            padding: 10px;
            margin: 5px 0;
            background: #f8f9fa;
            border-radius: 8px;
            display: flex;
            align-items: center;
        }

        .list-icon {
            margin-right: 10px;
            font-size: 1.2em;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }

        .resource-meter {
            display: flex;
            align-items: center;
            margin: 10px 0;
        }

        .resource-label {
            width: 80px;
            font-weight: 600;
            color: #555;
        }

        .resource-bar {
            flex: 1;
            margin: 0 15px;
        }

        .resource-value {
            width: 60px;
            text-align: right;
            font-weight: 600;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 15px;
        }

        .stat-box {
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }

        .stat-number {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
        }

        .stat-label {
            font-size: 0.85em;
            color: #666;
            margin-top: 5px;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .updating {
            animation: pulse 1s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 System Dashboard</h1>
            <div class="last-updated" id="lastUpdated">Loading...</div>
        </div>

        <div class="grid">
            <!-- Auto-Confirm Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">🤖</span>
                    <span class="card-title">Auto-Confirm</span>
                    <span class="status-badge" id="autoConfirmBadge">Loading...</span>
                </div>
                <div id="autoConfirmContent">Loading...</div>
            </div>

            <!-- Tmux Sessions Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">💻</span>
                    <span class="card-title">Tmux Sessions</span>
                    <span class="status-badge status-running" id="tmuxBadge">0</span>
                </div>
                <div id="tmuxContent">Loading...</div>
            </div>

            <!-- Research Projects Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">🔍</span>
                    <span class="card-title">Research Projects</span>
                </div>
                <div id="projectsContent">Loading...</div>
            </div>

            <!-- Messaging Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">📱</span>
                    <span class="card-title">Messaging</span>
                </div>
                <div id="messagingContent">Loading...</div>
            </div>

            <!-- Verification Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">✓</span>
                    <span class="card-title">Verification</span>
                </div>
                <div id="verificationContent">Loading...</div>
            </div>

            <!-- System Resources Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">💾</span>
                    <span class="card-title">System Resources</span>
                </div>
                <div id="systemContent">Loading...</div>
            </div>

            <!-- Smart Routing Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">🎯</span>
                    <span class="card-title">Smart Routing</span>
                </div>
                <div id="routingContent">Loading...</div>
            </div>

            <!-- Auto-Confirm Activity Card -->
            <div class="card" style="grid-column: span 2;">
                <div class="card-header">
                    <span class="card-icon">🔐</span>
                    <span class="card-title">Auto-Confirm Activity</span>
                </div>
                <div id="autoConfirmActivityContent">Loading...</div>
            </div>
        </div>
    </div>

    <script>
        function getStatusColor(percent) {
            if (percent < 50) return '#28a745';
            if (percent < 80) return '#ffc107';
            return '#dc3545';
        }

        function updateDashboard() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Update timestamp
                    const timestamp = new Date(data.timestamp);
                    document.getElementById('lastUpdated').textContent =
                        `Last updated: ${timestamp.toLocaleTimeString()}`;

                    // Auto-Confirm
                    const ac = data.auto_confirm;
                    const acBadge = document.getElementById('autoConfirmBadge');
                    const acContent = document.getElementById('autoConfirmContent');

                    if (ac.running) {
                        acBadge.textContent = 'Running';
                        acBadge.className = 'status-badge status-running';
                        acContent.innerHTML = `
                            <div class="metric">
                                <div class="metric-label">Process ID</div>
                                <div class="metric-value">${ac.pid}</div>
                            </div>
                            <div class="stats-grid" style="grid-template-columns: 1fr 1fr;">
                                <div class="stat-box">
                                    <div class="stat-number">${ac.cpu_percent.toFixed(1)}%</div>
                                    <div class="stat-label">CPU</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-number">${ac.memory_mb.toFixed(1)}</div>
                                    <div class="stat-label">MB RAM</div>
                                </div>
                            </div>
                        `;
                    } else {
                        acBadge.textContent = 'Stopped';
                        acBadge.className = 'status-badge status-stopped';
                        acContent.innerHTML = '<div class="metric-value">Not running</div>';
                    }

                    // Tmux Sessions
                    const tmux = data.tmux;
                    document.getElementById('tmuxBadge').textContent = tmux.count;

                    let tmuxHtml = '';
                    if (tmux.sessions && tmux.sessions.length > 0) {
                        tmux.sessions.forEach(session => {
                            tmuxHtml += `
                                <div class="list-item">
                                    <span class="list-icon">•</span>
                                    <span>${session}</span>
                                </div>
                            `;
                        });
                        if (tmux.total > 5) {
                            tmuxHtml += `
                                <div class="list-item" style="background: transparent; font-style: italic;">
                                    ... and ${tmux.total - 5} more
                                </div>
                            `;
                        }
                    } else {
                        tmuxHtml = '<div class="metric-value">No sessions</div>';
                    }
                    document.getElementById('tmuxContent').innerHTML = tmuxHtml;

                    // Research Projects
                    const projects = data.research_projects;
                    let projectsHtml = '';
                    if (projects.length > 0) {
                        projects.forEach(proj => {
                            const icon = proj.status === 'complete' ? '✅' : '⏳';
                            const badgeClass = proj.status === 'complete' ? 'status-complete' : 'status-running';
                            projectsHtml += `
                                <div class="list-item">
                                    <span class="list-icon">${icon}</span>
                                    <div style="flex: 1;">
                                        <div style="font-weight: 600;">${proj.name}</div>
                                        <div style="font-size: 0.85em; color: #666;">${proj.topics} topics</div>
                                    </div>
                                    <span class="status-badge ${badgeClass}">${proj.status}</span>
                                </div>
                            `;
                        });
                    } else {
                        projectsHtml = '<div class="metric-value">No projects</div>';
                    }
                    document.getElementById('projectsContent').innerHTML = projectsHtml;

                    // Messaging
                    const msg = data.messaging;
                    let msgHtml = `
                        <div class="metric">
                            <div class="metric-label">Total Messages</div>
                            <div class="metric-value">${msg.total_messages}</div>
                        </div>
                    `;
                    if (msg.by_backend && Object.keys(msg.by_backend).length > 0) {
                        msgHtml += '<div style="margin-top: 15px;">';
                        for (const [backend, count] of Object.entries(msg.by_backend)) {
                            msgHtml += `
                                <div class="list-item">
                                    <span class="list-icon">📤</span>
                                    <span>${backend}: ${count}</span>
                                </div>
                            `;
                        }
                        msgHtml += '</div>';
                    }
                    document.getElementById('messagingContent').innerHTML = msgHtml;

                    // Verification
                    const ver = data.verification;
                    document.getElementById('verificationContent').innerHTML = `
                        <div class="metric">
                            <div class="metric-label">Success Rate</div>
                            <div class="metric-value">${ver.success_rate}</div>
                        </div>
                        <div class="stats-grid">
                            <div class="stat-box">
                                <div class="stat-number">${ver.total}</div>
                                <div class="stat-label">Total</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-number" style="color: #28a745;">${ver.verified}</div>
                                <div class="stat-label">Verified</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-number" style="color: #dc3545;">${ver.failed}</div>
                                <div class="stat-label">Failed</div>
                            </div>
                        </div>
                    `;

                    // System Resources
                    const sys = data.system;
                    document.getElementById('systemContent').innerHTML = `
                        <div class="resource-meter">
                            <div class="resource-label">CPU</div>
                            <div class="resource-bar">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${sys.cpu_percent}%; background: ${getStatusColor(sys.cpu_percent)};"></div>
                                </div>
                            </div>
                            <div class="resource-value">${sys.cpu_percent.toFixed(1)}%</div>
                        </div>
                        <div class="resource-meter">
                            <div class="resource-label">Memory</div>
                            <div class="resource-bar">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${sys.memory_percent}%; background: ${getStatusColor(sys.memory_percent)};"></div>
                                </div>
                            </div>
                            <div class="resource-value">${sys.memory_percent.toFixed(1)}%</div>
                        </div>
                        <div class="resource-meter">
                            <div class="resource-label">Disk</div>
                            <div class="resource-bar">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${sys.disk_percent}%; background: ${getStatusColor(sys.disk_percent)};"></div>
                                </div>
                            </div>
                            <div class="resource-value">${sys.disk_percent.toFixed(1)}%</div>
                        </div>
                    `;

                    // Smart Routing
                    const routing = data.routing;
                    let routingHtml = '';
                    if (routing && routing.total_routes > 0) {
                        routingHtml = `
                            <div class="metric">
                                <div class="metric-label">Total Routes</div>
                                <div class="metric-value">${routing.total_routes}</div>
                            </div>
                            <div class="stats-grid">
                                <div class="stat-box">
                                    <div class="stat-number" style="color: #667eea;">${routing.by_target.claude || 0}</div>
                                    <div class="stat-label">Claude</div>
                                    <div style="font-size: 0.75em; color: #999; margin-top: 3px;">${routing.distribution.claude || '0%'}</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-number" style="color: #764ba2;">${routing.by_target.perplexity || 0}</div>
                                    <div class="stat-label">Perplexity</div>
                                    <div style="font-size: 0.75em; color: #999; margin-top: 3px;">${routing.distribution.perplexity || '0%'}</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-number" style="color: #28a745;">${routing.by_target.comet || 0}</div>
                                    <div class="stat-label">Comet</div>
                                    <div style="font-size: 0.75em; color: #999; margin-top: 3px;">${routing.distribution.comet || '0%'}</div>
                                </div>
                            </div>
                        `;
                    } else {
                        routingHtml = '<div class="metric-value">No routes yet</div>';
                    }
                    document.getElementById('routingContent').innerHTML = routingHtml;

                    // Auto-Confirm Activity
                    const ac_activity = data.auto_confirm_activity;
                    let acActivityHtml = '';
                    if (ac_activity && ac_activity.total_prompts > 0) {
                        acActivityHtml = `
                            <div class="stats-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 20px;">
                                <div class="stat-box">
                                    <div class="stat-number">${ac_activity.total_prompts}</div>
                                    <div class="stat-label">Total Prompts</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-number" style="color: #28a745;">${ac_activity.auto_approved || 0}</div>
                                    <div class="stat-label">Auto-Approved</div>
                                    <div style="font-size: 0.75em; color: #999; margin-top: 3px;">${ac_activity.approval_rate}</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-number" style="color: #ffc107;">${ac_activity.manually_confirmed || 0}</div>
                                    <div class="stat-label">Manual</div>
                                    <div style="font-size: 0.75em; color: #999; margin-top: 3px;">${ac_activity.manual_rate}</div>
                                </div>
                                <div class="stat-box">
                                    <div class="stat-number" style="color: #dc3545;">${ac_activity.rejected || 0}</div>
                                    <div class="stat-label">Rejected</div>
                                    <div style="font-size: 0.75em; color: #999; margin-top: 3px;">${ac_activity.rejection_rate}</div>
                                </div>
                            </div>
                            <div style="font-size: 0.9em; color: #666;">
                                <div>Most Common Tool: <strong>${ac_activity.most_common_tool || 'N/A'}</strong></div>
                                <div style="margin-top: 5px;">Most Common Risk: <strong>${ac_activity.most_common_risk || 'N/A'}</strong></div>
                            </div>
                        `;
                    } else {
                        acActivityHtml = '<div class="metric-value">No activity yet</div>';
                    }
                    document.getElementById('autoConfirmActivityContent').innerHTML = acActivityHtml;
                })
                .catch(error => {
                    console.error('Error fetching status:', error);
                });
        }

        // Initial update
        updateDashboard();

        // Auto-refresh every 5 seconds
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Serve the dashboard HTML."""
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/status")
def api_status():
    """Get current system status as JSON."""
    status = dashboard.get_status()

    # Add routing stats if available
    try:
        routing_stats = router.get_stats()
        status["routing"] = routing_stats
    except:
        status["routing"] = None

    # Add auto-confirm stats
    try:
        ac_stats = ac_monitor.get_stats()
        status["auto_confirm_activity"] = ac_stats
    except:
        status["auto_confirm_activity"] = None

    # Add quality stats
    try:
        quality_stats = scorer.get_stats()
        status["quality"] = quality_stats
    except:
        status["quality"] = None

    # Add scraper stats
    try:
        scraper_stats = scraper.get_stats()
        status["scraper"] = scraper_stats
    except:
        status["scraper"] = None

    return jsonify(status)


@app.route("/api/auto-confirm/activity")
def api_auto_confirm_activity():
    """Get recent auto-confirm activity."""
    limit = int(request.args.get("limit", 20))
    minutes = request.args.get("minutes")
    if minutes:
        minutes = int(minutes)

    activity = ac_monitor.get_recent_activity(limit=limit, minutes=minutes)
    return jsonify(activity)


@app.route("/api/auto-confirm/stats")
def api_auto_confirm_stats():
    """Get auto-confirm statistics."""
    stats = ac_monitor.get_stats()
    return jsonify(stats)


@app.route("/api/quality/stats")
def api_quality_stats():
    """Get quality scoring statistics."""
    stats = scorer.get_stats()
    return jsonify(stats)


@app.route("/api/quality/comparison")
def api_quality_comparison():
    """Get source quality comparison."""
    comparison = scorer.compare_sources()
    return jsonify(comparison)


@app.route("/api/scraper/stats")
def api_scraper_stats():
    """Get scraper statistics."""
    stats = scraper.get_stats()
    return jsonify(stats)


@app.route("/api/scraper/recent")
def api_scraper_recent():
    """Get recent scraped results."""
    limit = int(request.args.get("limit", 10))
    results = scraper.get_recent_results(limit=limit)
    return jsonify(results)


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# Session Monitoring API Endpoints
@app.route("/api/monitor/status")
def api_monitor_status():
    """Get foundation session monitor status."""
    if not session_monitor:
        return jsonify({"error": "Session monitor not available", "available": False}), 503

    try:
        status = session_monitor.get_status_summary()
        status["available"] = True
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e), "available": False}), 500


@app.route("/api/monitor/assign-task", methods=["POST"])
def api_monitor_assign_task():
    """Manually assign a task to the foundation session."""
    if not session_monitor:
        return jsonify({"error": "Session monitor not available"}), 503

    try:
        data = request.get_json()
        if not data or "task" not in data:
            return jsonify({"error": "Missing 'task' field"}), 400

        task = {
            "id": "manual",
            "content": data["task"],
            "priority": data.get("priority", 100),
            "category": data.get("category", "manual"),
        }

        success = session_monitor.send_task_to_session(task)

        if success:
            return jsonify({"success": True, "task": task, "message": "Task assigned successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to send task to session"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/monitor/work-log")
def api_monitor_work_log():
    """Get work log entries."""
    try:
        from pathlib import Path

        log_file = Path(__file__).parent / "logs" / "foundation_work.log"

        if not log_file.exists():
            return jsonify({"entries": [], "count": 0})

        limit = int(request.args.get("limit", 50))

        with open(log_file, "r") as f:
            lines = f.readlines()

        # Get last N lines
        recent_lines = lines[-limit:] if len(lines) > limit else lines

        entries = []
        for line in recent_lines:
            if line.strip():
                entries.append(line.strip())

        return jsonify({"entries": entries, "count": len(entries), "total_lines": len(lines)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/monitor/check-and-assign")
def api_monitor_check_and_assign():
    """Trigger a check and assignment cycle."""
    if not session_monitor:
        return jsonify({"error": "Session monitor not available"}), 503

    try:
        session_monitor.check_and_assign_work()
        return jsonify({"success": True, "message": "Check and assign cycle completed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Claude Integration API Endpoints
@app.route("/api/claude/status")
def api_claude_status():
    """Check if Claude session is ready."""
    try:
        is_ready, msg = claude.check_session_ready()
        return jsonify({"ready": is_ready, "status": msg, "session": claude.session_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/claude/execute", methods=["POST"])
def api_claude_execute():
    """Execute a task on Claude."""
    try:
        data = request.get_json()
        if not data or "task" not in data:
            return jsonify({"error": "Missing 'task' field"}), 400

        task = data["task"]
        timeout = data.get("timeout", 120)

        result = claude.execute_task(task, timeout=timeout)

        if result:
            return jsonify(result)
        else:
            return jsonify({"error": "Failed to execute task"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/claude/stats")
def api_claude_stats():
    """Get Claude execution statistics."""
    try:
        stats = claude.get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/claude/recent")
def api_claude_recent():
    """Get recent Claude results."""
    try:
        limit = int(request.args.get("limit", 10))
        results = claude.get_recent_results(limit=limit)
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Result Comparison API Endpoints
@app.route("/api/compare/execute", methods=["POST"])
def api_compare_execute():
    """Execute and compare results from all sources."""
    try:
        data = request.get_json()
        if not data or "query" not in data:
            return jsonify({"error": "Missing 'query' field"}), 400

        query = data["query"]
        timeout = data.get("timeout", 120)

        comparison = comparator.compare_all(query, timeout=timeout)
        return jsonify(comparison)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/compare/stats")
def api_compare_stats():
    """Get comparison statistics."""
    try:
        stats = comparator.get_comparison_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/compare/recent")
def api_compare_recent():
    """Get recent comparisons."""
    try:
        limit = int(request.args.get("limit", 10))
        comparisons = comparator.get_recent_comparisons(limit=limit)
        return jsonify({"comparisons": comparisons, "count": len(comparisons)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Comet Integration API Endpoints
@app.route("/api/comet/status")
def api_comet_status():
    """Check if Comet browser is running."""
    try:
        running = comet.check_browser_running()
        return jsonify({"running": running, "browser": comet.browser_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/comet/launch", methods=["POST"])
def api_comet_launch():
    """Launch Comet browser."""
    try:
        success = comet.launch_browser()
        return jsonify({"success": success, "running": comet.check_browser_running()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/comet/execute", methods=["POST"])
def api_comet_execute():
    """Execute a query on Comet."""
    try:
        data = request.get_json()
        if not data or "query" not in data:
            return jsonify({"error": "Missing 'query' field"}), 400

        query = data["query"]
        timeout = data.get("timeout", 60)

        result = comet.execute_task(query, timeout=timeout)

        if result:
            return jsonify(result)
        else:
            return jsonify({"error": "Failed to execute query"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/comet/stats")
def api_comet_stats():
    """Get Comet execution statistics."""
    try:
        stats = comet.get_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/comet/recent")
def api_comet_recent():
    """Get recent Comet results."""
    try:
        limit = int(request.args.get("limit", 10))
        results = comet.get_recent_results(limit=limit)
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import sys

    # Allow port override via --port argument
    port = 8080
    if "--port" in sys.argv:
        try:
            port_idx = sys.argv.index("--port")
            port = int(sys.argv[port_idx + 1])
        except (IndexError, ValueError):
            pass

    feature_env = os.environ.get("FEATURE_ENV", "main")

    print("\n" + "=" * 80)
    print("🚀 WEB DASHBOARD STARTING")
    print("=" * 80)
    print()
    print(f"Environment: {feature_env}")
    print(f"📊 Dashboard URL: http://localhost:{port}")
    print("🔄 Auto-refresh: Every 5 seconds")
    print(f"📡 API Endpoint: http://localhost:{port}/api/status")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 80 + "\n")

    app.run(host="0.0.0.0", port=port, debug=False)
