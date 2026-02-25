# Data Organization

All project data is organized in this folder.

## Structure

```
data/
├── ethiopia/              # Ethiopia trip research project
│   ├── ethiopia_prompts.json
│   └── ethiopia_results/  # Research responses
│
├── property_analysis/     # Property analysis project
│   └── property_analysis_project.json
│
└── framework/             # Generic automation framework
    └── automation.db      # Database with sources, prompt trees, executions
```

## Projects

### Ethiopia Trip (June 2026)
- **Status**: Active
- **Research Topics**: 7 (Flights, Hotels, Tigray, Activities, Documents, Budget, Packing)
- **Data**: `ethiopia/`

### Property Analysis
- **Status**: Created
- **Research Topics**: 5 (Value, Income, Loan, Cash Flow, Risk)
- **Data**: `property_analysis/`

### Framework
- **Database**: SQLite with automation configuration
- **Tables**: sources, elements, actions, prompt_trees, executions
- **Purpose**: Reusable automation flows

## Usage

Scripts automatically look for data in these folders:
- `ethiopia_*.py` → `data/ethiopia/`
- `run_property_analysis.py` → `data/property_analysis/`
- Framework executor → `data/framework/automation.db`

## Concurrent Projects

Multiple projects can run simultaneously. Each project has:
- Separate data folder
- Separate execution tracking in framework DB
- Independent Google Sheet tracking
