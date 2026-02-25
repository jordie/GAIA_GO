#!/usr/bin/env python3
"""
Setup automation framework with Ethiopia trip planning examples
"""

import sqlite3
import json
from pathlib import Path

db_path = 'automation.db'

# Initialize database
conn = sqlite3.connect(db_path)

# Load schema
with open('schema.sql') as f:
    conn.executescript(f.read())

# Insert Perplexity source
conn.execute('''
INSERT OR REPLACE INTO sources (name, type, base_url, app_name, description)
VALUES (?, ?, ?, ?, ?)
''', ('perplexity', 'browser', 'https://www.perplexity.ai', 'Comet', 
      'Perplexity AI search interface'))

source_id = conn.execute('SELECT id FROM sources WHERE name = ?', ('perplexity',)).fetchone()[0]

# Insert elements
elements = [
    ('search_box', 'tab', 'key', 'Main search input', 0.4),
    ('submit', 'return', 'key', 'Submit search', 1.0),
    ('focus_search', 'f', 'key', 'Focus search (Cmd+F)', 0.3),
]

for name, selector, sel_type, desc, wait in elements:
    conn.execute('''
    INSERT OR REPLACE INTO elements (source_id, name, selector, selector_type, description, wait_after)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (source_id, name, selector, sel_type, desc, wait))

# Insert actions
actions = [
    ('activate_browser', 'applescript', 'Activate Comet browser', 
     'tell application "Comet" to activate'),
    
    ('focus_search', 'applescript', 'Focus search box',
     'tell application "System Events" to keystroke "f" using {command down}'),
    
    ('paste_text', 'clipboard', 'Paste text from clipboard',
     json.dumps({'action': 'paste'})),
    
    ('submit_form', 'applescript', 'Submit with Enter key',
     'tell application "System Events" to keystroke return'),
    
    ('next_tab', 'applescript', 'Move to next browser tab',
     'tell application "System Events" to keystroke "]" using {command down, shift down}'),
    
    ('wait_standard', 'wait', 'Standard wait period', None),
]

for name, atype, desc, impl in actions:
    conn.execute('''
    INSERT OR REPLACE INTO actions (name, type, description, implementation)
    VALUES (?, ?, ?, ?)
    ''', (name, atype, desc, impl))

# Create Ethiopia prompt tree
conn.execute('''
INSERT OR REPLACE INTO prompt_trees (name, source_id, description, steps, variables)
VALUES (?, ?, ?, ?, ?)
''', ('ethiopia_research', source_id, 'Submit research prompts to Perplexity',
      json.dumps([
          {'action': 'activate_browser', 'wait': 0.5},
          {'action': 'focus_search', 'wait': 0.3},
          {'action': 'paste_text', 'var': 'prompt'},
          {'action': 'submit_form', 'wait': 1.0},
          {'action': 'next_tab', 'wait': 0.5},
      ]),
      json.dumps(['prompt'])))

conn.commit()
conn.close()

print("✅ Framework database initialized")
print("📁 Database: automation.db")
print()
print("Sources added: Perplexity")
print("Actions added: 6")
print("Trees added: ethiopia_research")
