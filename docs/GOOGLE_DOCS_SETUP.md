# Google Docs API Setup Guide

## Quick Setup (5 minutes)

### Step 1: Create Service Account (if not already done)

Since you already have Google Sheets working, you likely have a service account set up at:
```
~/.config/gspread/service_account.json
```

The same credentials work for Google Docs!

### Step 2: Enable Google Docs API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (same one used for Sheets)
3. Navigate to **APIs & Services** → **Library**
4. Search for "Google Docs API"
5. Click **Enable**

### Step 3: Share Document with Service Account

1. Open your service account JSON file:
   ```bash
   cat ~/.config/gspread/service_account.json | jq -r '.client_email'
   ```

2. Copy the email address (looks like: `your-service@project-id.iam.gserviceaccount.com`)

3. Open your Google Doc:
   https://docs.google.com/document/d/1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w/edit

4. Click **Share** button

5. Paste the service account email

6. Set permission to **Editor**

7. Uncheck "Notify people"

8. Click **Share**

### Step 4: Test Connection

```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Read current document
python3 scripts/add_to_google_doc.py \
  --doc "https://docs.google.com/document/d/1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w/edit" \
  --read
```

## Usage Examples

### Add Clarification Questions

```bash
python3 scripts/add_to_google_doc.py \
  --doc "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w" \
  --file docs/CLARIFICATION_QUESTIONS.md \
  --title "Clarification" \
  --page-break
```

### Add Research Report

```bash
python3 scripts/add_to_google_doc.py \
  --doc "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w" \
  --file docs/MULTI_AGENT_ORCHESTRATION_RESEARCH_2026.md \
  --title "Multi-Agent Orchestration Research 2026" \
  --page-break
```

### Add Both Documents

```bash
# Add clarification first
python3 scripts/add_to_google_doc.py \
  --doc "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w" \
  --file docs/CLARIFICATION_QUESTIONS.md \
  --title "Clarification" \
  --page-break

# Then add research
python3 scripts/add_to_google_doc.py \
  --doc "1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w" \
  --file docs/MULTI_AGENT_ORCHESTRATION_RESEARCH_2026.md \
  --title "Multi-Agent Orchestration Research 2026" \
  --page-break
```

## Troubleshooting

### Error: "Credentials not found"

Make sure service account JSON exists:
```bash
ls -la ~/.config/gspread/service_account.json
```

If missing, you need to create a service account and download credentials.

### Error: "Permission denied" or 403

The service account doesn't have access to the document. Share the document with the service account email.

### Error: "Google Docs API has not been used"

Enable the Google Docs API in your Google Cloud Console project.

## Python API Reference

### Direct Usage in Code

```python
from utils.google_docs_client import GoogleDocsClient, extract_doc_id_from_url

# Initialize client
client = GoogleDocsClient()

# Extract doc ID from URL
doc_id = extract_doc_id_from_url(
    "https://docs.google.com/document/d/1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w/edit"
)

# Read document
content = client.read_doc(doc_id)

# Append content
client.append_to_doc(doc_id, "# New Section\n\nContent here...")

# Create a new section (like a tab)
client.create_tab(doc_id, "Research Findings", "Content for this section...")

# Replace all content
client.replace_content(doc_id, "# Completely New Document\n\n...")

# Insert at beginning
client.insert_at_index(doc_id, index=1, text="This goes at the start\n")

# Apply formatting
client.apply_formatting(
    doc_id,
    start_index=1,
    end_index=10,
    bold=True,
    font_size=16
)
```

## Architecture Integration

### Use in Architect Dashboard

```python
# In app.py or appropriate module
from utils.google_docs_client import GoogleDocsClient

@app.route('/api/export-to-gdoc', methods=['POST'])
def export_to_gdoc():
    data = request.get_json()
    doc_id = data['doc_id']
    content = data['content']
    title = data.get('title', 'Export')

    client = GoogleDocsClient()
    client.create_tab(doc_id, title, content)

    return jsonify({'success': True, 'doc_url': f'https://docs.google.com/document/d/{doc_id}/edit'})
```

### Use in Workers

```python
# In workers/milestone_worker.py
from utils.google_docs_client import GoogleDocsClient

def export_milestone_plan(milestone_data, doc_id):
    """Export milestone plan to Google Doc."""
    client = GoogleDocsClient()

    markdown = generate_milestone_markdown(milestone_data)

    client.create_tab(
        doc_id,
        f"Milestone: {milestone_data['name']}",
        markdown
    )
```

## Dependencies

Already installed (shared with Google Sheets):
- `google-auth`
- `google-api-python-client`

To install if missing:
```bash
pip install google-auth google-api-python-client
```

## Service Account Permissions

The service account needs these API scopes:
- `https://www.googleapis.com/auth/documents` (read/write docs)
- `https://www.googleapis.com/auth/drive` (access shared docs)

These are automatically configured in the `GoogleDocsClient`.
