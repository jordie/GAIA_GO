# Setup Pink Laptop for Multi-Computer Tab Group Sync

## Overview
This setup allows you to sync tab groups from the pink laptop to the same Google Sheet, keeping all your work organized across multiple computers.

## Setup Steps

### 1. Install Prerequisites on Pink Laptop

```bash
# Install Python packages
pip3 install gspread google-auth google-auth-oauthlib websockets

# Verify installation
python3 -c "import gspread; print('✓ gspread installed')"
```

### 2. Copy Google Credentials

The credentials should already exist at:
```
~/.config/gspread/service_account.json
```

If not, copy from Mac Mini:
```bash
# On Mac Mini
scp ~/.config/gspread/service_account.json user@pink-laptop:~/.config/gspread/
```

### 3. Copy Browser Automation Scripts

```bash
# On pink laptop, create directory
mkdir -p ~/browser_automation
cd ~/browser_automation

# Copy from Mac Mini (or clone from git)
scp user@mac-mini:/path/to/architect/workers/browser_automation/*.py .
```

Required files:
- `sync_multi_computer.py` - Main sync script
- `list_tab_groups.py` - List current tab groups

### 4. Setup Comet Browser Extension

The browser extension should already be installed and running on localhost:8765.

Verify:
```bash
# Check if WebSocket server is running
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Host: localhost:8765" \
  -H "Origin: http://localhost:8765" \
  http://localhost:8765/
```

Should return WebSocket upgrade response.

### 5. Run Your First Sync

```bash
cd ~/browser_automation

# List current tab groups
python3 list_tab_groups.py

# Sync to Google Sheet
python3 sync_multi_computer.py
```

Expected output:
```
💻 Computer: Pink MacBook
✓ Connected to Google Sheets
✓ Found X tab groups
✅ SYNC COMPLETE!
```

### 6. Verify in Google Sheet

Open the sheet:
https://docs.google.com/spreadsheets/d/1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q/edit

Check:
- **Tab Groups** worksheet → "Source Computer" column should show "Pink MacBook"
- **Tabs** worksheet → "Source Computer" column should show "Pink MacBook"

## Usage Workflow

### Daily Sync Routine

```bash
# Morning: Check what's in your sheet
open "https://docs.google.com/spreadsheets/d/1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q/edit"

# Work on tasks, create tab groups in Comet

# Sync when you have new research/progress
python3 sync_multi_computer.py

# Continue a conversation from the sheet:
# 1. Find the Perplexity URL in "Tabs" or "Conversations" worksheet
# 2. Click the URL
# 3. Conversation loads with full history
# 4. Keep working!

# Update status in sheet
# Mark tabs/groups as "completed" when done
```

### Working Across Computers

**Scenario: Start on Mac Mini, continue on Pink Laptop**

1. **On Mac Mini:**
   - Research flight options for Ethiopia trip
   - Ask Perplexity questions
   - Run `python3 sync_multi_computer.py`
   - Perplexity conversation URL synced to sheet

2. **Switch to Pink Laptop:**
   - Open Google Sheet
   - Go to "Conversations" tab
   - Find "Ethiopia flights" conversation
   - Click Perplexity URL
   - Conversation loads → continue exactly where you left off!

3. **On Pink Laptop:**
   - Continue the conversation
   - Add more research
   - Run `python3 sync_multi_computer.py`
   - Updates sync back to sheet

4. **Back on Mac Mini:**
   - Open sheet
   - See pink laptop updates
   - Click conversation URL
   - Continue!

## Multi-Computer Features

### Source Computer Tracking

Every tab and tab group is tagged with its source computer:
- **Mac Mini (Gezabase)** - Your main desktop
- **Pink MacBook** - Laptop
- Other computers auto-detected by hostname

### Filtering by Computer

In Google Sheet:
1. Click column header "Source Computer"
2. Filter → select specific computer
3. See only tabs from that machine

### No Duplicates

The sync system:
- Detects existing tabs by URL + source computer
- Updates existing entries instead of duplicating
- Preserves your manual edits (status, notes, etc.)

### Merge Strategy

- **New tab groups** → Added to sheet
- **Existing tab groups** → Updated with latest tab count, Perplexity URLs
- **Status/Progress** → Preserved from sheet (not overwritten)
- **Notes** → Preserved from sheet

## Troubleshooting

### Pink Laptop Not Detected

The script auto-detects "Pink MacBook" if hostname contains "macbook".

To manually set computer name, edit `sync_multi_computer.py`:
```python
def get_computer_name():
    return "Pink MacBook"  # Hardcode it
```

### No Tab Groups Found

Check:
1. Comet browser is running
2. Extension is active
3. WebSocket server running on port 8765
4. You have tab groups created in Comet

### Sync Conflicts

If both computers sync simultaneously:
- Last write wins
- Manual edits (status, notes) preserved
- Re-run sync to get latest state

## Advanced: Automated Sync

Setup cron job to auto-sync every 30 minutes:

```bash
# Edit crontab
crontab -e

# Add this line
*/30 * * * * cd ~/browser_automation && python3 sync_multi_computer.py >> sync.log 2>&1
```

Now your tab groups auto-sync every 30 minutes!

## Sheet Structure

Your Google Sheet has these tabs:

1. **Projects** - Top-level projects (e.g., "Ethiopia Trip")
2. **Tab Groups** - Sub-tasks within projects
3. **Tabs** - Individual browser tabs with URLs
4. **Conversations** - All Perplexity conversation URLs
5. **Instructions** - How to use the system
6. **groups** (legacy) - Original import
7. **Sheet1** (legacy) - Original data

**Main workflows use:** Projects → Tab Groups → Tabs → Conversations

## Next Steps

1. ✅ Sync from pink laptop
2. Create your first project (e.g., "Ethiopia Trip")
3. Organize tab groups into projects
4. Start tracking Perplexity conversations
5. Work seamlessly across computers!

## Support

If you encounter issues:
1. Check this README
2. Run `python3 list_tab_groups.py` to debug
3. Verify Google credentials exist
4. Check WebSocket server is running
