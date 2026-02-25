# ============================================================================
# PROJECT PORTFOLIO VIEW MODULE
# ============================================================================

import json
from datetime import datetime, timedelta

PORTFOLIO_CATEGORIES = {
    "strategic": {"label": "Strategic Initiatives", "color": "#9C27B0", "icon": "target"},
    "operational": {"label": "Operational", "color": "#2196F3", "icon": "settings"},
    "maintenance": {"label": "Maintenance", "color": "#FF9800", "icon": "tool"},
    "innovation": {"label": "Innovation/R&D", "color": "#4CAF50", "icon": "lightbulb"},
    "compliance": {"label": "Compliance/Security", "color": "#F44336", "icon": "shield"},
    "infrastructure": {"label": "Infrastructure", "color": "#607D8B", "icon": "server"},
    "customer": {"label": "Customer-Facing", "color": "#00BCD4", "icon": "users"},
    "internal": {"label": "Internal Tools", "color": "#795548", "icon": "box"},
}


def get_project_metrics(conn, project_id):
    """Calculate all metrics for a single project."""
    # Health score
    score = 100
    bugs = conn.execute(
        "SELECT SUM(CASE WHEN status='open' AND severity='critical' THEN 12 "
        "WHEN status='open' AND severity='high' THEN 6 ELSE 0 END) as penalty FROM bugs WHERE project_id=?",
        (project_id,),
    ).fetchone()
    score -= min(bugs["penalty"] or 0, 40)

    features = conn.execute(
        "SELECT COUNT(*) as t, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as c "
        "FROM features WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if features["t"]:
        score += min((features["c"] or 0) / features["t"] * 20, 20)
    score = max(0, min(100, score))

    total_features = features["t"] or 0
    completed_features = features["c"] or 0
    progress = (completed_features / total_features * 100) if total_features > 0 else 0

    milestones = conn.execute(
        """
        SELECT COUNT(*) as total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN target_date < date('now') AND status != 'completed' THEN 1 ELSE 0 END) as overdue,
               MIN(CASE WHEN status != 'completed' THEN target_date END) as next_deadline
        FROM milestones WHERE project_id=?
    """,
        (project_id,),
    ).fetchone()

    bug_counts = conn.execute(
        """
        SELECT COUNT(*) as total, SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END) as critical,
               SUM(CASE WHEN severity='high' THEN 1 ELSE 0 END) as high
        FROM bugs WHERE project_id=? AND status='open'
    """,
        (project_id,),
    ).fetchone()

    recent_updates = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT 1 FROM features WHERE project_id=? AND updated_at > datetime('now', '-7 days')
            UNION ALL SELECT 1 FROM bugs WHERE project_id=? AND updated_at > datetime('now', '-7 days')
        )
    """,
        (project_id, project_id),
    ).fetchone()[0]

    health_status = (
        "excellent"
        if score >= 85
        else (
            "healthy"
            if score >= 70
            else ("warning" if score >= 55 else ("at_risk" if score >= 40 else "critical"))
        )
    )

    return {
        "health_score": round(score, 1),
        "health_status": health_status,
        "progress": round(progress, 1),
        "features": {"total": total_features, "completed": completed_features},
        "milestones": {
            "total": milestones["total"] or 0,
            "completed": milestones["completed"] or 0,
            "overdue": milestones["overdue"] or 0,
            "next_deadline": milestones["next_deadline"],
        },
        "bugs": {
            "total": bug_counts["total"] or 0,
            "critical": bug_counts["critical"] or 0,
            "high": bug_counts["high"] or 0,
        },
        "recent_updates": recent_updates,
    }


def get_project_category(project):
    """Extract category from project metadata."""
    category = "operational"
    metadata = project.get("metadata")
    if metadata:
        try:
            meta = json.loads(metadata) if isinstance(metadata, str) else metadata
            category = meta.get("category", "operational")
        except:
            pass
    return category


def get_portfolio_overview(
    conn, group_by="category", include_archived=False, sort_by="priority", sort_order="desc"
):
    """Get portfolio overview with all projects and aggregated metrics."""
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))

    query = "SELECT * FROM projects"
    if not include_archived:
        query += " WHERE status != 'archived'"

    projects = conn.execute(query).fetchall()
    project_data = []

    for p in projects:
        proj = dict(p)
        proj["metrics"] = get_project_metrics(conn, p["id"])
        proj["category"] = get_project_category(p)
        project_data.append(proj)

    # Sort projects
    sort_key_map = {
        "name": lambda x: x.get("name", "").lower(),
        "priority": lambda x: x.get("priority", 0),
        "health": lambda x: x["metrics"]["health_score"],
        "progress": lambda x: x["metrics"]["progress"],
        "updated": lambda x: x.get("updated_at", ""),
    }
    sort_fn = sort_key_map.get(sort_by, sort_key_map["priority"])
    project_data.sort(key=sort_fn, reverse=(sort_order == "desc"))

    # Group projects
    groups = {}
    if group_by == "category":
        for proj in project_data:
            cat = proj.get("category", "operational")
            if cat not in groups:
                groups[cat] = {
                    "info": PORTFOLIO_CATEGORIES.get(
                        cat, {"label": cat.title(), "color": "#9E9E9E"}
                    ),
                    "projects": [],
                }
            groups[cat]["projects"].append(proj)
    elif group_by == "status":
        status_info = {
            "active": {"label": "Active", "color": "#4CAF50"},
            "paused": {"label": "Paused", "color": "#FF9800"},
            "completed": {"label": "Completed", "color": "#2196F3"},
            "archived": {"label": "Archived", "color": "#9E9E9E"},
        }
        for proj in project_data:
            st = proj.get("status", "active")
            if st not in groups:
                groups[st] = {
                    "info": status_info.get(st, {"label": st.title(), "color": "#9E9E9E"}),
                    "projects": [],
                }
            groups[st]["projects"].append(proj)
    elif group_by == "priority":
        priority_info = {
            "critical": {"label": "Critical", "color": "#9C27B0"},
            "high": {"label": "High", "color": "#F44336"},
            "medium": {"label": "Medium", "color": "#FF9800"},
            "low": {"label": "Low", "color": "#4CAF50"},
        }
        for proj in project_data:
            p = proj.get("priority", 0)
            prio = "critical" if p >= 5 else ("high" if p >= 4 else ("medium" if p >= 2 else "low"))
            if prio not in groups:
                groups[prio] = {"info": priority_info[prio], "projects": []}
            groups[prio]["projects"].append(proj)
    elif group_by == "health":
        health_info = {
            "excellent": {"label": "Excellent", "color": "#4CAF50"},
            "healthy": {"label": "Healthy", "color": "#8BC34A"},
            "warning": {"label": "Warning", "color": "#FF9800"},
            "at_risk": {"label": "At Risk", "color": "#FF5722"},
            "critical": {"label": "Critical", "color": "#F44336"},
        }
        for proj in project_data:
            h = proj["metrics"]["health_status"]
            if h not in groups:
                groups[h] = {"info": health_info[h], "projects": []}
            groups[h]["projects"].append(proj)
    else:
        groups["all"] = {
            "info": {"label": "All Projects", "color": "#2196F3"},
            "projects": project_data,
        }

    # Calculate portfolio-wide metrics
    total_projects = len(project_data)
    if total_projects:
        avg_health = sum(p["metrics"]["health_score"] for p in project_data) / total_projects
        avg_progress = sum(p["metrics"]["progress"] for p in project_data) / total_projects
    else:
        avg_health = avg_progress = 0

    total_features = sum(p["metrics"]["features"]["total"] for p in project_data)
    completed_features = sum(p["metrics"]["features"]["completed"] for p in project_data)
    total_bugs = sum(p["metrics"]["bugs"]["total"] for p in project_data)
    critical_bugs = sum(p["metrics"]["bugs"]["critical"] for p in project_data)
    overdue_milestones = sum(p["metrics"]["milestones"]["overdue"] for p in project_data)

    portfolio_metrics = {
        "total_projects": total_projects,
        "by_status": {
            s: len([p for p in project_data if p.get("status") == s])
            for s in ["active", "paused", "completed", "archived"]
        },
        "avg_health_score": round(avg_health, 1),
        "avg_progress": round(avg_progress, 1),
        "total_features": total_features,
        "completed_features": completed_features,
        "feature_completion_rate": round(completed_features / total_features * 100, 1)
        if total_features
        else 0,
        "total_open_bugs": total_bugs,
        "critical_bugs": critical_bugs,
        "overdue_milestones": overdue_milestones,
        "projects_at_risk": len(
            [p for p in project_data if p["metrics"]["health_status"] in ["critical", "at_risk"]]
        ),
    }

    return {
        "groups": groups,
        "metrics": portfolio_metrics,
        "categories": PORTFOLIO_CATEGORIES,
        "group_by": group_by,
    }


def get_portfolio_summary(conn):
    """Get compact portfolio summary for dashboard widgets."""
    import sqlite3

    conn.row_factory = sqlite3.Row

    status_counts = conn.execute(
        "SELECT status, COUNT(*) as count FROM projects GROUP BY status"
    ).fetchall()
    by_status = {r["status"]: r["count"] for r in status_counts}

    features = conn.execute(
        """
        SELECT COUNT(*) as total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed
        FROM features f JOIN projects p ON f.project_id = p.id WHERE p.status = 'active'
    """
    ).fetchone()

    bugs = conn.execute(
        """
        SELECT COUNT(*) as total, SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END) as critical,
               SUM(CASE WHEN severity='high' THEN 1 ELSE 0 END) as high
        FROM bugs b JOIN projects p ON b.project_id = p.id WHERE b.status = 'open' AND p.status = 'active'
    """
    ).fetchone()

    overdue = conn.execute(
        """
        SELECT COUNT(*) FROM milestones m JOIN projects p ON m.project_id = p.id
        WHERE m.target_date < date('now') AND m.status != 'completed' AND p.status = 'active'
    """
    ).fetchone()[0]

    upcoming = conn.execute(
        """
        SELECT COUNT(*) FROM milestones m JOIN projects p ON m.project_id = p.id
        WHERE m.target_date BETWEEN date('now') AND date('now', '+7 days') AND m.status != 'completed' AND p.status = 'active'
    """
    ).fetchone()[0]

    recent_activity = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT 1 FROM features WHERE updated_at > datetime('now', '-24 hours')
            UNION ALL SELECT 1 FROM bugs WHERE updated_at > datetime('now', '-24 hours')
        )
    """
    ).fetchone()[0]

    return {
        "projects": {
            "total": sum(by_status.values()),
            "active": by_status.get("active", 0),
            "by_status": by_status,
        },
        "features": {
            "total": features["total"] or 0,
            "completed": features["completed"] or 0,
            "completion_rate": round((features["completed"] or 0) / features["total"] * 100, 1)
            if features["total"]
            else 0,
        },
        "bugs": {
            "open": bugs["total"] or 0,
            "critical": bugs["critical"] or 0,
            "high": bugs["high"] or 0,
        },
        "milestones": {"overdue": overdue, "upcoming_7d": upcoming},
        "activity": {"updates_24h": recent_activity},
    }


def get_portfolio_timeline(conn, start_date=None, end_date=None, include_completed=False):
    """Get portfolio timeline/roadmap view."""
    import sqlite3

    conn.row_factory = sqlite3.Row

    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    query = """
        SELECT m.*, p.name as project_name, p.status as project_status
        FROM milestones m JOIN projects p ON m.project_id = p.id
        WHERE m.target_date BETWEEN ? AND ? AND p.status != 'archived'
    """
    params = [start_date, end_date]
    if not include_completed:
        query += " AND m.status != 'completed'"
    query += " ORDER BY m.target_date ASC"

    milestones = conn.execute(query, params).fetchall()

    timeline = {}
    for m in milestones:
        date_obj = datetime.strptime(m["target_date"], "%Y-%m-%d") if m["target_date"] else None
        if date_obj:
            month_key = date_obj.strftime("%Y-%m")
            if month_key not in timeline:
                timeline[month_key] = {"month": date_obj.strftime("%B %Y"), "items": []}
            item = dict(m)
            item["is_overdue"] = (
                m["target_date"] < datetime.now().strftime("%Y-%m-%d")
                and m["status"] != "completed"
            )
            item["days_until"] = (date_obj - datetime.now()).days
            timeline[month_key]["items"].append(item)

    projects_timeline = conn.execute(
        """
        SELECT id, name, status, start_date, target_end_date, created_at FROM projects
        WHERE status != 'archived' AND (start_date IS NOT NULL OR target_end_date IS NOT NULL)
    """
    ).fetchall()

    return {
        "timeline": timeline,
        "projects": [dict(p) for p in projects_timeline],
        "range": {"start": start_date, "end": end_date},
        "today": datetime.now().strftime("%Y-%m-%d"),
    }


def get_portfolio_comparison(conn, project_ids, metrics_filter=None):
    """Compare multiple projects side by side."""
    import sqlite3

    conn.row_factory = sqlite3.Row

    comparison = []
    for pid in project_ids:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        if not project:
            continue

        proj = {
            "id": pid,
            "name": project["name"],
            "status": project["status"],
            "priority": project["priority"],
        }
        proj["metrics"] = {}

        metrics = get_project_metrics(conn, pid)

        if not metrics_filter or "health" in metrics_filter:
            proj["metrics"]["health"] = {
                "score": metrics["health_score"],
                "status": metrics["health_status"],
            }
        if not metrics_filter or "progress" in metrics_filter:
            proj["metrics"]["progress"] = {
                "percentage": metrics["progress"],
                "completed": metrics["features"]["completed"],
                "total": metrics["features"]["total"],
            }
        if not metrics_filter or "bugs" in metrics_filter:
            proj["metrics"]["bugs"] = metrics["bugs"]
        if not metrics_filter or "milestones" in metrics_filter:
            proj["metrics"]["milestones"] = metrics["milestones"]
        if not metrics_filter or "activity" in metrics_filter:
            activity_7d = conn.execute(
                "SELECT COUNT(*) FROM (SELECT 1 FROM features WHERE project_id=? AND updated_at > datetime('now', '-7 days') "
                "UNION ALL SELECT 1 FROM bugs WHERE project_id=? AND updated_at > datetime('now', '-7 days'))",
                (pid, pid),
            ).fetchone()[0]
            activity_30d = conn.execute(
                "SELECT COUNT(*) FROM (SELECT 1 FROM features WHERE project_id=? AND updated_at > datetime('now', '-30 days') "
                "UNION ALL SELECT 1 FROM bugs WHERE project_id=? AND updated_at > datetime('now', '-30 days'))",
                (pid, pid),
            ).fetchone()[0]
            proj["metrics"]["activity"] = {"updates_7d": activity_7d, "updates_30d": activity_30d}

        comparison.append(proj)

    return {"projects": comparison, "compared_ids": project_ids}


def get_portfolio_risks(conn):
    """Get portfolio-wide risk assessment."""
    import sqlite3

    conn.row_factory = sqlite3.Row
    risks = []

    # Overdue milestones
    overdue_milestones = conn.execute(
        """
        SELECT m.*, p.name as project_name FROM milestones m JOIN projects p ON m.project_id = p.id
        WHERE m.target_date < date('now') AND m.status != 'completed' AND p.status = 'active' ORDER BY m.target_date ASC
    """
    ).fetchall()
    for m in overdue_milestones:
        days_overdue = (datetime.now() - datetime.strptime(m["target_date"], "%Y-%m-%d")).days
        risks.append(
            {
                "type": "overdue_milestone",
                "severity": "high" if days_overdue > 14 else "medium",
                "project_id": m["project_id"],
                "project_name": m["project_name"],
                "item_id": m["id"],
                "item_name": m["name"],
                "message": f"Milestone '{m['name']}' is {days_overdue} days overdue",
                "days_overdue": days_overdue,
            }
        )

    # Critical bugs
    critical_bugs = conn.execute(
        """
        SELECT b.*, p.name as project_name FROM bugs b JOIN projects p ON b.project_id = p.id
        WHERE b.severity = 'critical' AND b.status = 'open' AND p.status = 'active' ORDER BY b.created_at ASC
    """
    ).fetchall()
    for b in critical_bugs:
        age_days = (
            (datetime.now() - datetime.strptime(b["created_at"][:10], "%Y-%m-%d")).days
            if b["created_at"]
            else 0
        )
        risks.append(
            {
                "type": "critical_bug",
                "severity": "critical",
                "project_id": b["project_id"],
                "project_name": b["project_name"],
                "item_id": b["id"],
                "item_name": b["title"],
                "message": f"Critical bug '{b['title']}' open for {age_days} days",
                "age_days": age_days,
            }
        )

    # Stale projects
    stale_projects = conn.execute(
        """
        SELECT p.id, p.name, p.updated_at,
               (SELECT MAX(updated_at) FROM features WHERE project_id = p.id) as last_feature_update,
               (SELECT MAX(updated_at) FROM bugs WHERE project_id = p.id) as last_bug_update
        FROM projects p WHERE p.status = 'active'
    """
    ).fetchall()
    for p in stale_projects:
        last_update = max(
            filter(None, [p["updated_at"], p["last_feature_update"], p["last_bug_update"]]),
            default=None,
        )
        if last_update:
            try:
                last_date = datetime.strptime(last_update[:10], "%Y-%m-%d")
                days_stale = (datetime.now() - last_date).days
                if days_stale >= 14:
                    risks.append(
                        {
                            "type": "stale_project",
                            "severity": "medium" if days_stale < 30 else "high",
                            "project_id": p["id"],
                            "project_name": p["name"],
                            "message": f"Project '{p['name']}' has no activity for {days_stale} days",
                            "days_stale": days_stale,
                        }
                    )
            except:
                pass

    # Poor health projects
    projects = conn.execute("SELECT id, name FROM projects WHERE status = 'active'").fetchall()
    for p in projects:
        metrics = get_project_metrics(conn, p["id"])
        if metrics["health_score"] < 40:
            risks.append(
                {
                    "type": "poor_health",
                    "severity": "critical" if metrics["health_score"] < 25 else "high",
                    "project_id": p["id"],
                    "project_name": p["name"],
                    "message": f"Project '{p['name']}' health score is {int(metrics['health_score'])}%",
                    "health_score": int(metrics["health_score"]),
                }
            )

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    risks.sort(key=lambda r: severity_order.get(r["severity"], 4))

    summary = {
        "total_risks": len(risks),
        "by_severity": {
            s: len([r for r in risks if r["severity"] == s])
            for s in ["critical", "high", "medium", "low"]
        },
        "by_type": {},
    }
    for r in risks:
        summary["by_type"][r["type"]] = summary["by_type"].get(r["type"], 0) + 1

    return {"risks": risks, "summary": summary}


def get_portfolio_allocation(conn):
    """Get resource allocation view across portfolio."""
    import sqlite3

    conn.row_factory = sqlite3.Row

    projects = conn.execute(
        """
        SELECT p.id, p.name, p.status, p.priority,
               (SELECT COUNT(*) FROM features WHERE project_id = p.id AND status != 'completed') as open_features,
               (SELECT COUNT(*) FROM features WHERE project_id = p.id AND status = 'in_progress') as in_progress_features,
               (SELECT COUNT(*) FROM bugs WHERE project_id = p.id AND status = 'open') as open_bugs,
               (SELECT COUNT(*) FROM milestones WHERE project_id = p.id AND status != 'completed') as open_milestones
        FROM projects p WHERE p.status = 'active' ORDER BY p.priority DESC
    """
    ).fetchall()

    allocation = []
    total_work = 0
    for p in projects:
        work_items = (p["open_features"] or 0) + (p["open_bugs"] or 0)
        total_work += work_items
        allocation.append(
            {
                "project_id": p["id"],
                "name": p["name"],
                "priority": p["priority"],
                "open_features": p["open_features"] or 0,
                "in_progress": p["in_progress_features"] or 0,
                "open_bugs": p["open_bugs"] or 0,
                "open_milestones": p["open_milestones"] or 0,
                "total_work_items": work_items,
            }
        )

    for item in allocation:
        item["work_percentage"] = (
            round(item["total_work_items"] / total_work * 100, 1) if total_work else 0
        )

    return {
        "allocation": allocation,
        "totals": {
            "projects": len(allocation),
            "work_items": total_work,
            "features": sum(a["open_features"] for a in allocation),
            "bugs": sum(a["open_bugs"] for a in allocation),
        },
    }


def get_portfolio_categories_usage(conn):
    """Get available portfolio categories and their usage."""
    projects = conn.execute(
        "SELECT id, metadata FROM projects WHERE status != 'archived'"
    ).fetchall()
    category_counts = {cat: 0 for cat in PORTFOLIO_CATEGORIES}
    category_counts["uncategorized"] = 0

    for p in projects:
        category = "uncategorized"
        if p[1]:
            try:
                meta = json.loads(p[1]) if isinstance(p[1], str) else p[1]
                category = meta.get("category", "uncategorized")
            except:
                pass
        if category in category_counts:
            category_counts[category] += 1
        else:
            category_counts["uncategorized"] += 1

    return {"categories": PORTFOLIO_CATEGORIES, "usage": category_counts}


def set_project_category(conn, project_id, category):
    """Set the portfolio category for a project."""
    if category and category not in PORTFOLIO_CATEGORIES:
        raise ValueError(
            f"Invalid category. Valid options: {', '.join(PORTFOLIO_CATEGORIES.keys())}"
        )

    project = conn.execute("SELECT metadata FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return None

    try:
        metadata = json.loads(project[0]) if project[0] else {}
    except:
        metadata = {}

    metadata["category"] = category
    conn.execute(
        "UPDATE projects SET metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (json.dumps(metadata), project_id),
    )

    return category
