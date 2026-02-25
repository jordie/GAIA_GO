"""
Project Cost Tracking Module
Track budgets, expenses, and cost analysis for projects
"""

import json
from datetime import datetime, timedelta

# Cost categories
COST_CATEGORIES = {
    "labor": "Labor/Personnel",
    "infrastructure": "Infrastructure/Hosting",
    "software": "Software/Licenses",
    "hardware": "Hardware/Equipment",
    "services": "External Services",
    "travel": "Travel/Expenses",
    "training": "Training/Education",
    "marketing": "Marketing/Advertising",
    "legal": "Legal/Compliance",
    "misc": "Miscellaneous",
}

# Cost status options
COST_STATUSES = ["planned", "approved", "committed", "spent", "cancelled"]


def create_project_budget(
    conn, project_id, budget_amount, currency="USD", fiscal_year=None, notes=None, created_by=None
):
    """Create or update project budget."""
    cursor = conn.cursor()

    # Verify project exists
    cursor.execute("SELECT id, name FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()
    if not project:
        return {"error": "Project not found"}

    fiscal_year = fiscal_year or datetime.now().year

    # Check if budget exists for this project/year
    cursor.execute(
        """
        SELECT id FROM project_budgets
        WHERE project_id = ? AND fiscal_year = ?
    """,
        (project_id, fiscal_year),
    )

    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE project_budgets
            SET budget_amount = ?, currency = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (budget_amount, currency, notes, existing["id"]),
        )
        budget_id = existing["id"]
    else:
        cursor.execute(
            """
            INSERT INTO project_budgets (project_id, budget_amount, currency, fiscal_year, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (project_id, budget_amount, currency, fiscal_year, notes, created_by),
        )
        budget_id = cursor.lastrowid

    conn.commit()

    return {
        "id": budget_id,
        "project_id": project_id,
        "project_name": project["name"],
        "budget_amount": budget_amount,
        "currency": currency,
        "fiscal_year": fiscal_year,
    }


def get_project_budget(conn, project_id, fiscal_year=None):
    """Get project budget with spending summary."""
    cursor = conn.cursor()

    fiscal_year = fiscal_year or datetime.now().year

    cursor.execute(
        """
        SELECT b.*, p.name as project_name
        FROM project_budgets b
        JOIN projects p ON b.project_id = p.id
        WHERE b.project_id = ? AND b.fiscal_year = ?
    """,
        (project_id, fiscal_year),
    )

    budget = cursor.fetchone()
    if not budget:
        return None

    result = dict(budget)

    # Get spending by category
    cursor.execute(
        """
        SELECT category, status,
               SUM(amount) as total_amount,
               COUNT(*) as entry_count
        FROM project_costs
        WHERE project_id = ? AND fiscal_year = ?
        GROUP BY category, status
    """,
        (project_id, fiscal_year),
    )

    by_category = {}
    by_status = {"planned": 0, "approved": 0, "committed": 0, "spent": 0}

    for row in cursor.fetchall():
        cat = row["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "by_status": {}}
        by_category[cat]["total"] += row["total_amount"]
        by_category[cat]["by_status"][row["status"]] = row["total_amount"]

        if row["status"] in by_status:
            by_status[row["status"]] += row["total_amount"]

    total_spent = by_status["spent"]
    total_committed = by_status["committed"] + total_spent
    budget_amount = result["budget_amount"]

    result["spending"] = {
        "by_category": by_category,
        "by_status": by_status,
        "total_spent": total_spent,
        "total_committed": total_committed,
        "remaining": budget_amount - total_committed,
        "utilization_percent": round(total_spent / budget_amount * 100, 1)
        if budget_amount > 0
        else 0,
        "commitment_percent": round(total_committed / budget_amount * 100, 1)
        if budget_amount > 0
        else 0,
    }

    return result


def add_cost_entry(
    conn,
    project_id,
    amount,
    category,
    description,
    cost_date=None,
    status="planned",
    vendor=None,
    invoice_ref=None,
    fiscal_year=None,
    metadata=None,
    created_by=None,
):
    """Add a cost entry to a project."""
    cursor = conn.cursor()

    # Verify project exists
    cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not cursor.fetchone():
        return {"error": "Project not found"}

    if category not in COST_CATEGORIES:
        return {"error": f'Invalid category. Must be one of: {", ".join(COST_CATEGORIES.keys())}'}

    if status not in COST_STATUSES:
        return {"error": f'Invalid status. Must be one of: {", ".join(COST_STATUSES)}'}

    cost_date = cost_date or datetime.now().strftime("%Y-%m-%d")
    fiscal_year = fiscal_year or datetime.now().year

    cursor.execute(
        """
        INSERT INTO project_costs (project_id, amount, category, description, cost_date,
                                   status, vendor, invoice_ref, fiscal_year, metadata, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            project_id,
            amount,
            category,
            description,
            cost_date,
            status,
            vendor,
            invoice_ref,
            fiscal_year,
            json.dumps(metadata) if metadata else None,
            created_by,
        ),
    )

    cost_id = cursor.lastrowid
    conn.commit()

    return {
        "id": cost_id,
        "project_id": project_id,
        "amount": amount,
        "category": category,
        "description": description,
        "cost_date": cost_date,
        "status": status,
    }


def update_cost_entry(conn, cost_id, updates):
    """Update a cost entry."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM project_costs WHERE id = ?", (cost_id,))
    if not cursor.fetchone():
        return {"error": "Cost entry not found"}

    allowed_fields = [
        "amount",
        "category",
        "description",
        "cost_date",
        "status",
        "vendor",
        "invoice_ref",
        "metadata",
    ]

    set_clauses = []
    params = []

    for field in allowed_fields:
        if field in updates:
            value = updates[field]
            if field == "category" and value not in COST_CATEGORIES:
                return {"error": f"Invalid category"}
            if field == "status" and value not in COST_STATUSES:
                return {"error": f"Invalid status"}
            if field == "metadata" and value is not None:
                value = json.dumps(value)
            set_clauses.append(f"{field} = ?")
            params.append(value)

    if not set_clauses:
        return {"error": "No valid fields to update"}

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(cost_id)

    query = f'UPDATE project_costs SET {", ".join(set_clauses)} WHERE id = ?'
    cursor.execute(query, params)
    conn.commit()

    return get_cost_entry(conn, cost_id)


def get_cost_entry(conn, cost_id):
    """Get a single cost entry."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.*, p.name as project_name
        FROM project_costs c
        JOIN projects p ON c.project_id = p.id
        WHERE c.id = ?
    """,
        (cost_id,),
    )

    row = cursor.fetchone()
    return dict(row) if row else None


def delete_cost_entry(conn, cost_id):
    """Delete a cost entry."""
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM project_costs WHERE id = ?", (cost_id,))
    if not cursor.fetchone():
        return {"error": "Cost entry not found"}

    cursor.execute("DELETE FROM project_costs WHERE id = ?", (cost_id,))
    conn.commit()

    return {"success": True, "deleted_id": cost_id}


def get_project_costs(
    conn, project_id, fiscal_year=None, category=None, status=None, start_date=None, end_date=None
):
    """Get all cost entries for a project."""
    cursor = conn.cursor()

    query = """
        SELECT c.*, p.name as project_name
        FROM project_costs c
        JOIN projects p ON c.project_id = p.id
        WHERE c.project_id = ?
    """
    params = [project_id]

    if fiscal_year:
        query += " AND c.fiscal_year = ?"
        params.append(fiscal_year)

    if category:
        query += " AND c.category = ?"
        params.append(category)

    if status:
        query += " AND c.status = ?"
        params.append(status)

    if start_date:
        query += " AND c.cost_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND c.cost_date <= ?"
        params.append(end_date)

    query += " ORDER BY c.cost_date DESC, c.created_at DESC"

    cursor.execute(query, params)
    entries = [dict(row) for row in cursor.fetchall()]

    total = sum(e["amount"] for e in entries)

    return {"entries": entries, "count": len(entries), "total_amount": total}


def get_cost_summary(conn, fiscal_year=None, group_by="project"):
    """Get cost summary across all projects."""
    cursor = conn.cursor()

    fiscal_year = fiscal_year or datetime.now().year

    if group_by == "project":
        cursor.execute(
            """
            SELECT p.id as project_id, p.name as project_name,
                   b.budget_amount,
                   SUM(CASE WHEN c.status = 'spent' THEN c.amount ELSE 0 END) as spent,
                   SUM(CASE WHEN c.status IN ('committed', 'spent') THEN c.amount ELSE 0 END) as committed,
                   SUM(c.amount) as total_costs,
                   COUNT(c.id) as entry_count
            FROM projects p
            LEFT JOIN project_budgets b ON p.id = b.project_id AND b.fiscal_year = ?
            LEFT JOIN project_costs c ON p.id = c.project_id AND c.fiscal_year = ?
            GROUP BY p.id
            HAVING total_costs > 0 OR b.budget_amount > 0
            ORDER BY total_costs DESC
        """,
            (fiscal_year, fiscal_year),
        )

    elif group_by == "category":
        cursor.execute(
            """
            SELECT c.category,
                   SUM(CASE WHEN c.status = 'spent' THEN c.amount ELSE 0 END) as spent,
                   SUM(CASE WHEN c.status IN ('committed', 'spent') THEN c.amount ELSE 0 END) as committed,
                   SUM(c.amount) as total_costs,
                   COUNT(c.id) as entry_count,
                   COUNT(DISTINCT c.project_id) as project_count
            FROM project_costs c
            WHERE c.fiscal_year = ?
            GROUP BY c.category
            ORDER BY total_costs DESC
        """,
            (fiscal_year,),
        )

    elif group_by == "month":
        cursor.execute(
            """
            SELECT strftime('%Y-%m', c.cost_date) as month,
                   SUM(CASE WHEN c.status = 'spent' THEN c.amount ELSE 0 END) as spent,
                   SUM(c.amount) as total_costs,
                   COUNT(c.id) as entry_count,
                   COUNT(DISTINCT c.project_id) as project_count
            FROM project_costs c
            WHERE c.fiscal_year = ?
            GROUP BY month
            ORDER BY month DESC
        """,
            (fiscal_year,),
        )

    elif group_by == "vendor":
        cursor.execute(
            """
            SELECT COALESCE(c.vendor, 'Unknown') as vendor,
                   SUM(CASE WHEN c.status = 'spent' THEN c.amount ELSE 0 END) as spent,
                   SUM(c.amount) as total_costs,
                   COUNT(c.id) as entry_count,
                   COUNT(DISTINCT c.project_id) as project_count
            FROM project_costs c
            WHERE c.fiscal_year = ?
            GROUP BY vendor
            ORDER BY total_costs DESC
        """,
            (fiscal_year,),
        )

    else:
        return {"error": f"Invalid group_by: {group_by}"}

    results = [dict(row) for row in cursor.fetchall()]

    # Calculate totals
    total_spent = sum(r.get("spent", 0) or 0 for r in results)
    total_committed = sum(r.get("committed", 0) or 0 for r in results)
    total_costs = sum(r.get("total_costs", 0) or 0 for r in results)

    # Get total budget
    cursor.execute(
        """
        SELECT SUM(budget_amount) as total_budget
        FROM project_budgets
        WHERE fiscal_year = ?
    """,
        (fiscal_year,),
    )
    budget_row = cursor.fetchone()
    total_budget = budget_row["total_budget"] or 0 if budget_row else 0

    return {
        "fiscal_year": fiscal_year,
        "group_by": group_by,
        "results": results,
        "totals": {
            "total_budget": total_budget,
            "total_spent": total_spent,
            "total_committed": total_committed,
            "total_costs": total_costs,
            "budget_remaining": total_budget - total_committed,
            "utilization_percent": round(total_spent / total_budget * 100, 1)
            if total_budget > 0
            else 0,
        },
    }


def get_budget_vs_actual(conn, project_id=None, fiscal_year=None):
    """Get budget vs actual spending comparison."""
    cursor = conn.cursor()

    fiscal_year = fiscal_year or datetime.now().year

    if project_id:
        cursor.execute(
            """
            SELECT p.id as project_id, p.name as project_name,
                   b.budget_amount, b.currency,
                   SUM(CASE WHEN c.status = 'spent' THEN c.amount ELSE 0 END) as actual_spent,
                   SUM(CASE WHEN c.status IN ('committed', 'spent') THEN c.amount ELSE 0 END) as committed
            FROM projects p
            LEFT JOIN project_budgets b ON p.id = b.project_id AND b.fiscal_year = ?
            LEFT JOIN project_costs c ON p.id = c.project_id AND c.fiscal_year = ?
            WHERE p.id = ?
            GROUP BY p.id
        """,
            (fiscal_year, fiscal_year, project_id),
        )
    else:
        cursor.execute(
            """
            SELECT p.id as project_id, p.name as project_name,
                   b.budget_amount, b.currency,
                   SUM(CASE WHEN c.status = 'spent' THEN c.amount ELSE 0 END) as actual_spent,
                   SUM(CASE WHEN c.status IN ('committed', 'spent') THEN c.amount ELSE 0 END) as committed
            FROM projects p
            LEFT JOIN project_budgets b ON p.id = b.project_id AND b.fiscal_year = ?
            LEFT JOIN project_costs c ON p.id = c.project_id AND c.fiscal_year = ?
            GROUP BY p.id
            HAVING b.budget_amount > 0 OR actual_spent > 0
            ORDER BY b.budget_amount DESC
        """,
            (fiscal_year, fiscal_year),
        )

    results = []
    for row in cursor.fetchall():
        data = dict(row)
        budget = data["budget_amount"] or 0
        spent = data["actual_spent"] or 0
        committed = data["committed"] or 0

        data["variance"] = budget - spent
        data["variance_percent"] = round((budget - spent) / budget * 100, 1) if budget > 0 else 0
        data["utilization_percent"] = round(spent / budget * 100, 1) if budget > 0 else 0
        data["status"] = (
            "over_budget"
            if spent > budget
            else "at_risk"
            if committed > budget * 0.9
            else "on_track"
        )

        results.append(data)

    return {
        "fiscal_year": fiscal_year,
        "comparisons": results,
        "summary": {
            "total_budget": sum(r["budget_amount"] or 0 for r in results),
            "total_spent": sum(r["actual_spent"] or 0 for r in results),
            "over_budget_count": sum(1 for r in results if r["status"] == "over_budget"),
            "at_risk_count": sum(1 for r in results if r["status"] == "at_risk"),
            "on_track_count": sum(1 for r in results if r["status"] == "on_track"),
        },
    }


def get_cost_forecast(conn, project_id, months=3):
    """Forecast future costs based on historical spending."""
    cursor = conn.cursor()

    # Get historical monthly spending
    cursor.execute(
        """
        SELECT strftime('%Y-%m', cost_date) as month,
               SUM(amount) as total
        FROM project_costs
        WHERE project_id = ? AND status = 'spent'
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
    """,
        (project_id,),
    )

    historical = [dict(row) for row in cursor.fetchall()]

    if len(historical) < 2:
        return {"error": "Insufficient historical data for forecast"}

    # Calculate average monthly spend
    avg_monthly = sum(h["total"] for h in historical) / len(historical)

    # Get current budget
    cursor.execute(
        """
        SELECT budget_amount FROM project_budgets
        WHERE project_id = ? AND fiscal_year = ?
    """,
        (project_id, datetime.now().year),
    )

    budget_row = cursor.fetchone()
    budget = budget_row["budget_amount"] if budget_row else 0

    # Get current spent
    cursor.execute(
        """
        SELECT SUM(amount) as spent FROM project_costs
        WHERE project_id = ? AND status = 'spent' AND fiscal_year = ?
    """,
        (project_id, datetime.now().year),
    )

    spent_row = cursor.fetchone()
    current_spent = spent_row["spent"] or 0 if spent_row else 0

    # Generate forecast
    forecasts = []
    cumulative = current_spent
    today = datetime.now()

    for i in range(1, months + 1):
        forecast_date = today + timedelta(days=30 * i)
        cumulative += avg_monthly
        forecasts.append(
            {
                "month": forecast_date.strftime("%Y-%m"),
                "projected_spend": round(avg_monthly, 2),
                "cumulative_spend": round(cumulative, 2),
                "budget_remaining": round(budget - cumulative, 2) if budget else None,
                "on_track": cumulative <= budget if budget else None,
            }
        )

    return {
        "project_id": project_id,
        "historical_avg_monthly": round(avg_monthly, 2),
        "current_spent": current_spent,
        "budget": budget,
        "forecasts": forecasts,
        "projected_year_end": round(current_spent + avg_monthly * (12 - today.month), 2),
    }


def get_labor_costs_from_worklog(
    conn, project_id, hourly_rate=None, start_date=None, end_date=None
):
    """Calculate labor costs from worklog entries."""
    cursor = conn.cursor()

    if not start_date:
        start_date = datetime.now().replace(month=1, day=1).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Get worklog hours for project tasks
    cursor.execute(
        """
        SELECT w.user_id,
               SUM(w.time_spent_minutes) as total_minutes,
               SUM(CASE WHEN w.billable THEN w.time_spent_minutes ELSE 0 END) as billable_minutes,
               COUNT(DISTINCT w.task_id) as task_count
        FROM task_worklog w
        JOIN task_queue t ON w.task_id = t.id
        WHERE t.project_id = ?
          AND w.work_date BETWEEN ? AND ?
        GROUP BY w.user_id
    """,
        (project_id, start_date, end_date),
    )

    labor_data = []
    total_hours = 0
    total_billable_hours = 0

    default_rate = hourly_rate or 50  # Default hourly rate

    for row in cursor.fetchall():
        hours = row["total_minutes"] / 60
        billable_hours = row["billable_minutes"] / 60
        cost = billable_hours * default_rate

        labor_data.append(
            {
                "user_id": row["user_id"],
                "total_hours": round(hours, 2),
                "billable_hours": round(billable_hours, 2),
                "task_count": row["task_count"],
                "hourly_rate": default_rate,
                "labor_cost": round(cost, 2),
            }
        )

        total_hours += hours
        total_billable_hours += billable_hours

    return {
        "project_id": project_id,
        "period": {"start": start_date, "end": end_date},
        "hourly_rate": default_rate,
        "by_user": labor_data,
        "totals": {
            "total_hours": round(total_hours, 2),
            "billable_hours": round(total_billable_hours, 2),
            "total_labor_cost": round(total_billable_hours * default_rate, 2),
        },
    }


def get_categories():
    """Get available cost categories."""
    return COST_CATEGORIES


def get_statuses():
    """Get available cost statuses."""
    return COST_STATUSES
