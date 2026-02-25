# Tab Groups Multi-Computer Tracking System

## Overview

Successfully set up a complete tab group tracking system that syncs tab groups from multiple computers to a Google Sheet, preserving Perplexity conversation URLs for continuing work across devices.

## Google Sheet
https://docs.google.com/spreadsheets/d/1b1H2aZdSpj_0I0UzMVDbdcBMTqXQ5mAgtJ88zlxLm-Q/edit

### Worksheets
1. **Projects** - Top-level organization
2. **Tab Groups** - Groups with status, progress, Perplexity URLs
3. **Tabs** - Individual tabs with URLs
4. **Conversations** - Perplexity conversation tracking
5. **Instructions** - How to use the system

## Current Tab Groups (from both computers)

### Mac Mini (Gezabase)
1. **find health...** (2 tabs)
   - Health information and plans

### Pink Laptop (jgirmay@Helus-Air.attlocal.net)
1. **this is...** (2 tabs) - School assignments
   - Google Apps Script project
   - Ezana Assignment Updates form
   - **Suggested Perplexity:** Date calculations, assignment planning

2. **find out...** (3 tabs) - Phone plans
   - AT&T website
   - Habtu Phone Line Cost spreadsheet
   - **Suggested Perplexity:** Phone plan comparisons, AT&T vs competitors

3. **pull out...** (2 tabs) - Healthcare
   - MyHealth at Stanford
   - Stanford Health Care orders & referrals
   - **Suggested Perplexity:** Stanford healthcare navigation, appointment scheduling

4. **DENTAL-MEDI** (1 tab) - Dental provider search
   - Provider Directory Search (Medi-Cal)
   - **Suggested Perplexity:** "Best Medi-Cal dental providers near me", "How to find dentist accepting Medi-Cal"

5. **try to...** (2 tabs) - Real estate
   - Off Market 5 unit in Alameda (7.66% Cap)
   - 1820 3rd St, Alameda property on Redfin
   - **Suggested Perplexity:** "Real estate cap rates explained", "Alameda property market analysis"

6. **my Name:...** (5 tabs) - Water damage repairs
   - Google Voice messages
   - Claude conversations
   - Thumbtack contractor messages
   - Unit 8 Water damage repairs spreadsheet
   - Mold removers search
   - **Suggested Perplexity:** "Water damage restoration best practices", "How to choose mold remediation contractor"

7. **get all...** (1 tab) - Task tracking
   - Javier Messages & Task Tracker spreadsheet
   - **Suggested Perplexity:** "Project management best practices", "Task tracking systems"

## Known Perplexity Conversations

From your Perplexity library (https://www.perplexity.ai/library):

1. **"how far is april 23rd from today?"**
   - https://www.perplexity.ai/search/how-far-is-april-23rd-from-tod-5rr4MPJGQWyc0wdxYpohBg
   - Could be related to: **this is...** (school assignments/deadlines)

2. **"give me a list of tab groups"**
   - https://www.perplexity.ai/search/give-me-a-list-of-tab-groups-6HKAK9qzTBy55q6mpAjuWg
   - Related to: **get all...** (tab management/organization)

3. **"ollama to automate web browsing"**
   - https://www.perplexity.ai/search/ollama-to-automate-web-browsin-ZNAYY4OaRFS8VkeERPniOA
   - General automation research

4. **Perplexity Library**
   - https://www.perplexity.ai/library
   - Your conversation history

## How to Add Perplexity Conversations to Tab Groups

### Method 1: Using the script
```bash
# List all tab groups
python3 add_perplexity_to_group.py list

# Add a Perplexity conversation to a group
python3 add_perplexity_to_group.py add 'DENTAL-MEDI' 'https://www.perplexity.ai/search/...' 'Best dentists'
```

### Method 2: Manual in Google Sheet
1. Open the Google Sheet
2. Go to "Tab Groups" worksheet
3. Find the group you want to update
4. Paste the Perplexity conversation URL in the "Main Perplexity URL" column

## Sync Workflow

### From Mac Mini
```bash
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect/workers/browser_automation
python3 sync_multi_computer.py
```

### From Pink Laptop
```bash
ssh jgirmay@100.108.134.121
cd ~/browser_automation
python3 sync_multi_computer.py
```

## Key Features

✅ **Multi-computer sync** - Tab groups from Mac Mini and Pink Laptop tracked separately
✅ **Source tracking** - "Source Computer" column shows which machine each group came from
✅ **Perplexity integration** - Store conversation URLs to continue research on any device
✅ **Smart merging** - Detects duplicates, preserves manual edits (status, notes, progress)
✅ **Tab group renaming** - Can rename groups using rename_tab_group.py
✅ **Full tab details** - All URLs, titles, and metadata preserved

## Next Steps

1. **Find relevant Perplexity conversations** in your library for each topic:
   - AT&T/phone plans → add to "find out..."
   - Healthcare/Stanford → add to "pull out..."
   - Dental/Medi-Cal → add to "DENTAL-MEDI"
   - Real estate/Alameda → add to "try to..."
   - Water damage/contractors → add to "my Name:..."

2. **Rename tab groups** to more descriptive names:
   ```bash
   python3 rename_tab_group.py <group_id> 'New Descriptive Name'
   ```

3. **Track progress** in the Google Sheet:
   - Update Status column (pending/in-progress/completed)
   - Mark completed tabs
   - Add notes and dependencies

4. **Continue work from any computer**:
   - Open Google Sheet
   - Click Perplexity URL
   - Conversation loads with full history
   - Keep working where you left off!

## Scripts Created

| Script | Purpose |
|--------|---------|
| `sync_multi_computer.py` | Sync tab groups to Google Sheet (both computers) |
| `list_tab_groups.py` | List all tab groups with details |
| `rename_tab_group.py` | Rename tab groups |
| `add_perplexity_to_group.py` | Add Perplexity conversation URLs to groups |
| `associate_conversations.py` | Show suggested conversation associations |
| `setup_complete_tracker.py` | Initial Google Sheet setup |
| `pull_from_pink_laptop.sh` | Quick script to pull tab groups from pink laptop |

## Database

- Google Sheet: Single source of truth for all tab groups
- WebSocket: Chrome extension on localhost:8765
- Service account credentials: ~/.config/gspread/service_account.json

## Example Use Case: Ethiopia Trip Planning

When you're ready to plan a big trip:

1. Create tab groups for different aspects:
   - "Tickets - Ethiopia Trip"
   - "Hotels - Addis Ababa"
   - "Activities - Ethiopia"
   - "Logistics - Travel"

2. Research each aspect in Perplexity, save conversation URLs

3. Sync to Google Sheet from any computer

4. Switch computers? Just open the sheet, click conversation URL, continue!

5. Mark items complete as you book them

6. Track overall progress percentage
