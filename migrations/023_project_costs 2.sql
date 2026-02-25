-- Project Cost Tracking Migration
-- Adds tables for budget and expense tracking

-- Table for project budgets
CREATE TABLE IF NOT EXISTS project_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    budget_amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    fiscal_year INTEGER NOT NULL,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, fiscal_year)
);

-- Indexes for budgets
CREATE INDEX IF NOT EXISTS idx_budgets_project ON project_budgets(project_id);
CREATE INDEX IF NOT EXISTS idx_budgets_year ON project_budgets(fiscal_year);

-- Table for project costs/expenses
CREATE TABLE IF NOT EXISTS project_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    cost_date DATE NOT NULL,
    status TEXT DEFAULT 'planned',
    vendor TEXT,
    invoice_ref TEXT,
    fiscal_year INTEGER NOT NULL,
    metadata TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Indexes for costs
CREATE INDEX IF NOT EXISTS idx_costs_project ON project_costs(project_id);
CREATE INDEX IF NOT EXISTS idx_costs_category ON project_costs(category);
CREATE INDEX IF NOT EXISTS idx_costs_status ON project_costs(status);
CREATE INDEX IF NOT EXISTS idx_costs_year ON project_costs(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_costs_date ON project_costs(cost_date);
