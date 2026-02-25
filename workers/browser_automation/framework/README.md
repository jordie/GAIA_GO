# Generic Browser Automation Framework

## Philosophy
Instead of writing scripts for each task, define **data** for sources and compose reusable **prompt trees**.

## Architecture

```
framework/
├── sources/           # Website/app definitions
│   ├── perplexity.yaml
│   ├── google_sheets.yaml
│   └── whatsapp.yaml
├── prompt_trees/      # Reusable navigation flows
│   ├── perplexity_submit.yaml
│   ├── sheet_update.yaml
│   └── whatsapp_send.yaml
├── actions/           # Generic action library
│   └── actions.py
├── lib/              # Core framework
│   ├── executor.py
│   └── tree_parser.py
└── run.py            # Main entry point
```

## Example Usage

```bash
# Execute a prompt tree
python3 run.py --source perplexity --tree submit_question --data prompt.json

# Compose trees
python3 run.py --tree compose --steps open_perplexity,submit,collect_url
```

## Source Definition (YAML)
Defines elements, delays, and navigation patterns for a website.

## Prompt Tree (YAML)
Defines a sequence of actions with decision points.

## Data File (JSON)
Runtime data injected into trees.
