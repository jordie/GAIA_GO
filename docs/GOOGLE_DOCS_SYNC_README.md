# Google Docs Auto-Sync

Automatically synchronize all markdown documentation to Google Docs.

## 🎯 Features

- ✅ Reads all `.md` files from `docs/` directory
- ✅ Converts markdown to Google Docs format
- ✅ Auto-generates table of contents
- ✅ Updates document with timestamp
- ✅ Service account authentication (no browser needed)
- ✅ Preview mode for testing
- ✅ Selective file sync

## 📋 Prerequisites

1. **Service Account Credentials**
   - Located at: `.config/google/credentials.json`
   - Email: `sheets-sync@homademics.iam.gserviceaccount.com`

2. **Share Google Doc**
   - ⚠️ **CRITICAL:** Share the target document with the service account
   - Document: https://docs.google.com/document/d/1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w/edit
   - Email to add: `sheets-sync@homademics.iam.gserviceaccount.com`
   - Permission: **Editor** (not Viewer!)

## 🚀 Usage

### Sync All Documentation

```bash
python3 docs/google_docs_sync.py
```

### Preview Without Writing

```bash
python3 docs/google_docs_sync.py --preview
```

### Sync Specific File

```bash
python3 docs/google_docs_sync.py --file ARCHITECT_SYSTEM_DOCUMENTATION.md
```

### Use Custom Document

```bash
python3 docs/google_docs_sync.py --doc-id YOUR_DOCUMENT_ID
```

## 📊 What Gets Synced

The script automatically includes:

1. **Header Section**
   - Document title
   - Auto-generation timestamp
   - Horizontal rule separator

2. **Table of Contents**
   - All markdown files listed
   - Auto-generated from filenames

3. **Full Content**
   - Each markdown file as a section
   - Section separators
   - Original formatting preserved

### Currently Syncing (18 files):

- `2026-02-05_llm_comparison_blocked.md`
- `2026-02-05_worker_scaling_validation.md`
- `AI_OPTIMIZATION_ANALYSIS.md`
- `ANYTHINGLLM_SETUP.md`
- `ARCHITECT_SYSTEM_DOCUMENTATION.md`
- `CLUSTER_SETUP.md`
- `COMPONENT_TYPES.md`
- `LLM_FULL_LIFECYCLE_TESTING.md`
- `LLM_METRICS_API.md`
- `LLM_TESTING_SYSTEM.md`
- `LOCAL_LLM_INFRASTRUCTURE.md`
- `MASTER_TEST_PROMPT.md`
- `RAPID_TESTING_GUIDE.md`
- `SELF_HEALING_SYSTEM.md`
- `SESSION_STRUCTURE_SOP.md`
- `SYSTEM_DESIGN_AUDIT_2026-02-08.md`
- `TROUBLESHOOTING.md`
- `UNSTABLE_SERVERS_REPORT_2026-02-08.md`

**Total:** ~237,000 characters

## ⏰ Automated Sync

### Option 1: Git Hook (Recommended)

Add to `.git/hooks/post-commit`:

```bash
#!/bin/bash
# Auto-sync docs to Google Docs after commit

cd "$(git rev-parse --show-toplevel)"
python3 docs/google_docs_sync.py --quiet
```

### Option 2: Cron Job

```bash
# Sync daily at 9 AM
0 9 * * * cd /path/to/architect && python3 docs/google_docs_sync.py >> logs/docs_sync.log 2>&1
```

### Option 3: GitHub Actions

```yaml
name: Sync Docs to Google
on:
  push:
    paths:
      - 'docs/**.md'
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Sync to Google Docs
        run: python3 docs/google_docs_sync.py
        env:
          GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
```

## 🔧 Troubleshooting

### Error: "Permission denied" (403)

**Problem:** Document not shared with service account

**Solution:**
1. Open: https://docs.google.com/document/d/1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w/edit
2. Click "Share" button
3. Add: `sheets-sync@homademics.iam.gserviceaccount.com`
4. Set permission to "Editor"
5. Click "Done"

### Error: "Credentials not found"

**Problem:** Missing credentials file

**Solution:**
```bash
# Copy from basic_edu_apps_final project
cp ../basic_edu_apps_final/.config/google/credentials.json .config/google/
```

### Error: "Authentication failed"

**Problem:** Invalid credentials or wrong file format

**Solution:**
- Verify credentials file is valid JSON
- Check it contains `type: "service_account"`
- Ensure file permissions are correct (readable)

## 📝 Output Example

```
📚 Google Docs Auto-Sync
============================================================

🔐 Authenticating with Google Docs API...
✅ Authenticated as: sheets-sync@homademics.iam.gserviceaccount.com

📂 Found 18 markdown file(s):
   - ARCHITECT_SYSTEM_DOCUMENTATION.md
   - ... (17 more files)

🔨 Building document content...
   Content length: 237548 characters

📝 Writing content to document...
✅ Successfully updated document!
📄 View at: https://docs.google.com/document/d/1I-cYYH6H3e36vpNSyrlkYobSna3CAkoxAoTTg4X4o7w/edit
```

## 🎓 Best Practices

1. **Preview First:** Always run with `--preview` before syncing
2. **Commit Often:** Add docs to git before syncing
3. **Check Output:** Verify Google Doc after sync
4. **Use Automation:** Set up git hooks or cron for automatic sync
5. **Keep Credentials Safe:** Never commit credentials to git

## 🔒 Security

- ✅ Credentials stored locally (not in git)
- ✅ Service account (no user tokens)
- ✅ Read-only access to credentials file
- ✅ HTTPS-only API communication
- ✅ `.gitignore` excludes `.config/`

## 📊 Statistics

- **Files synced:** 18 markdown files
- **Total content:** ~237 KB
- **Sync time:** ~2-3 seconds
- **API calls:** 2 (authenticate + update)

## 🆘 Support

For issues or questions:
- Check logs in `logs/docs_sync.log`
- Review Google Cloud Console for API errors
- Verify document sharing settings
- Test with `--preview` mode first
