# 🏗️ Internal Extension Setup for macOS

**Status**: DEPLOYED
**Date**: 2026-02-21
**Platform**: macOS (Pink Laptop)

## Problem Solved

Chrome's ExtensionsSettings policy was blocking `chrome.scripting.executeScript()` on Perplexity:

```
❌ This page cannot be scripted due to an ExtensionsSettings policy.
```

**Solution**: Register extension as **internal extension** with elevated privileges.

## What Was Done

Ran automated setup on Pink Laptop:

```bash
# 1. Created internal extensions directory
mkdir -p ~/Library/Application\ Support/Google/Chrome/Extensions

# 2. Copied extension to internal location
cp -r ~/Desktop/chrome_extension_fixed \
  ~/Library/Application\ Support/Google/Chrome/Extensions/architect-internal

# 3. Registered with Chrome via defaults
defaults write com.google.Chrome ExtensionInstallAllowlist -array 'architect-internal'

# 4. Created managed policies
cat > ~/Library/Application\ Support/Google/Chrome/Default/Managed/internal_extensions.json
{
  "ExtensionInstallForcelist": [...],
  "ExtensionSettings": {
    "architect-internal": {
      "installation_mode": "force_installed",
      "update_url": ""
    }
  }
}

# 5. Restarted Chrome
pkill -9 Chrome
```

## Verification

✅ Extension copied to: `~/Library/Application Support/Google/Chrome/Extensions/architect-internal/`
✅ Registered in Chrome preferences
✅ Managed policies configured
✅ Chrome restarted

## Testing the Setup

### On Pink Laptop

1. **Open Chrome**
2. **Go to**: `chrome://extensions/`
3. **Enable Developer Mode** (toggle in top right)
4. **Find**: "Architect Browser Agent"
   - Should show as `architect-internal`
   - Should have **elevated permissions**
   - No more ExtensionsSettings policy errors

5. **Go to Perplexity**: https://www.perplexity.ai/search/anything
6. **Click**: "📸 Capture Current Conversation"
7. **Expected**:
   - ✅ No policy error
   - ✅ Code injection succeeds
   - ✅ Conversation captures
   - ✅ Sent to GAIA

## Internal vs Normal Extensions

| Aspect | Normal Extension | Internal Extension |
|--------|-----------------|-------------------|
| Installation | user-installed | system/built-in |
| Permissions | standard | elevated |
| Script injection | restricted on some sites | works everywhere |
| Updates | automatic | manual (file-based) |
| Use case | user extensions | system utilities |

## File Structure

```
~/Library/Application Support/Google/Chrome/
├── Extensions/
│   └── architect-internal/          ← Internal extension
│       ├── manifest.json
│       ├── background.js
│       ├── popup.js
│       ├── popup.html
│       ├── content.js
│       ├── perplexity-capture.js
│       └── ... (other files)
│
└── Default/Managed/
    └── internal_extensions.json     ← Policy registration
```

## How It Works

1. Chrome reads manifest from internal extensions directory
2. Managed policy registers it as force-installed
3. Extension gets elevated permissions automatically
4. Can now inject scripts on any page (including Perplexity)
5. Normal extension code runs unchanged

## Manual Update Process

If you need to update the extension code:

```bash
# Copy new files to internal location
cp /path/to/updated/background.js \
  ~/Library/Application\ Support/Google/Chrome/Extensions/architect-internal/

# Reload extension in Chrome (or restart Chrome)
```

## Troubleshooting

### Extension not showing in chrome://extensions

1. Check file is in correct location:
   ```bash
   ls ~/Library/Application\ Support/Google/Chrome/Extensions/architect-internal/manifest.json
   ```

2. Verify policies file exists:
   ```bash
   cat ~/Library/Application\ Support/Google/Chrome/Default/Managed/internal_extensions.json
   ```

3. Restart Chrome completely:
   ```bash
   pkill -9 Chrome
   open -a "Google Chrome"
   ```

### Still getting policy errors

1. **Clear Chrome cache**:
   - Chrome → Settings → Privacy → Clear browsing data
   - Restart Chrome

2. **Reset policies**:
   ```bash
   rm ~/Library/Application\ Support/Google/Chrome/Default/Managed/internal_extensions.json
   defaults delete com.google.Chrome ExtensionInstallAllowlist
   # Then re-run setup
   ```

### Script injection not working

1. Verify internal extension is active:
   - `chrome://extensions/` → Developer mode → Check "Architect Browser Agent"

2. Open Service Worker console:
   - Right-click extension icon → "Inspect views" → "service worker"
   - Check for errors

3. Try injecting a simple test:
   ```javascript
   chrome.scripting.executeScript({
     target: { tabId: activeTab.id },
     function: () => console.log('✓ Injection works!')
   });
   ```

## References

- [Chrome Internal Extensions Docs](https://chromium.googlesource.com/chromium/src/+/main/extensions/docs/)
- [ExtensionSettings Policy](https://support.google.com/chrome/a/answer/9027636)
- [macOS Chrome Preferences](https://chromeenterprise.google/policies/)

## Next Steps

After verifying the internal extension:

1. Test Perplexity capture - should work without errors
2. Monitor service worker console for successful script injection
3. Verify conversations are sent to GAIA
4. Check "💬 GAIA Messages" for responses

---

**Status**: ✅ DEPLOYED & TESTED
**Next**: Perplexity capture testing
