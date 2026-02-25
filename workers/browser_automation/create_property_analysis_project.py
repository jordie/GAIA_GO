#!/usr/bin/env python3
"""
Create Property Analysis Project
"""
import sqlite3
import json
from datetime import datetime

# Connect to automation framework database
db_conn = sqlite3.connect('framework/automation.db')

# Also connect to any existing project tracking database
# For now, we'll use the framework database

# Create property analysis project
project_data = {
    "name": "Property Analysis - Income & Loan Calculator",
    "prompt": "Analyze this property and calculate income and if it supports 100% loan",
    "created_at": datetime.now().isoformat(),
    "status": "pending",
    "research_topics": [
        {
            "id": "PROP-001",
            "name": "Property Value Assessment",
            "prompt": """Analyze property value and market comparables:
- Current market value estimation
- Comparable properties in the area
- Recent sales data
- Property appreciation trends
- Market conditions and forecast"""
        },
        {
            "id": "PROP-002", 
            "name": "Income Potential Analysis",
            "prompt": """Calculate potential rental income:
- Market rental rates for similar properties
- Occupancy rate expectations
- Gross rental income projections
- Vacancy and maintenance costs
- Net operating income (NOI) calculation"""
        },
        {
            "id": "PROP-003",
            "name": "100% Loan Feasibility",
            "prompt": """Assess 100% loan to value (LTV) financing options:
- Current 100% LTV loan programs available
- USDA, VA, or specialized lending programs
- Income requirements for 100% financing
- Debt-to-income ratio calculations
- Credit score requirements
- Alternative financing strategies (seller financing, lease-to-own)"""
        },
        {
            "id": "PROP-004",
            "name": "Cash Flow Analysis",
            "prompt": """Calculate cash flow and investment returns:
- Monthly mortgage payment estimation (100% financing)
- Property taxes and insurance costs
- HOA fees and utilities
- Maintenance and repair reserves
- Total monthly expenses vs rental income
- Cash-on-cash return analysis
- Break-even analysis"""
        },
        {
            "id": "PROP-005",
            "name": "Investment Risk Assessment",
            "prompt": """Evaluate investment risks and considerations:
- Market volatility and economic factors
- Property condition and inspection needs
- Tenant risk and management requirements
- Interest rate sensitivity
- Exit strategy options
- Risk mitigation strategies"""
        }
    ]
}

# Save project data
with open('property_analysis_project.json', 'w') as f:
    json.dump(project_data, f, indent=2)

print("="*80)
print("PROPERTY ANALYSIS PROJECT CREATED")
print("="*80)
print()
print(f"Project: {project_data['name']}")
print(f"Status: {project_data['status']}")
print(f"Research Topics: {len(project_data['research_topics'])}")
print()
print("Topics:")
for topic in project_data['research_topics']:
    print(f"  {topic['id']}: {topic['name']}")
print()
print("Project file: property_analysis_project.json")
print()

# Add to framework database as a new prompt tree
cursor = db_conn.cursor()

# Check if perplexity source exists
source = cursor.execute("SELECT id FROM sources WHERE name = 'perplexity'").fetchone()
if source:
    source_id = source[0]
    
    # Create prompt tree for property analysis
    cursor.execute('''
        INSERT OR REPLACE INTO prompt_trees (name, source_id, description, steps, variables)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        'property_analysis',
        source_id,
        'Automated property analysis and loan feasibility research',
        json.dumps([
            {'action': 'activate_browser', 'wait': 0.5},
            {'action': 'focus_search', 'wait': 0.3},
            {'action': 'paste_text', 'var': 'prompt'},
            {'action': 'submit_form', 'wait': 1.0},
            {'action': 'next_tab', 'wait': 0.5},
        ]),
        json.dumps(['prompt', 'property_address'])
    ))
    
    db_conn.commit()
    print("✅ Added 'property_analysis' prompt tree to framework database")
else:
    print("⚠️  Perplexity source not found - run setup_framework.py first")

db_conn.close()

print()
print("="*80)
print("NEXT STEPS")
print("="*80)
print()
print("Option 1 - Manual Research:")
print("  Open each topic in Perplexity and paste the prompts")
print()
print("Option 2 - Automated (when you have property details):")
print("  python3 run_property_analysis.py --address '123 Main St'")
print()
print("Option 3 - Add to Google Sheet:")
print("  Update your tracking sheet with these topics")
print()
