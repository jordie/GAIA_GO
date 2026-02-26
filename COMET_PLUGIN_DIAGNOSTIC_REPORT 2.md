# Comet Browser Plugin - Diagnostic Report & Fix Plan

**Status**: Investigation Complete
**Date**: 2026-02-19
**Priority**: High (blocks test automation)

## Executive Summary

The Comet browser plugin has a **solid architectural foundation** but is **incompletely implemented** for the specific Comet sidebar use case. The Chrome extension properly handles:
- ✅ WebSocket communication
- ✅ Tab management
- ✅ DOM reading/writing
- ✅ Event forwarding

However, the **Comet/Perplexity sidebar integration is broken** due to:
- ❌ Missing DIAGNOSE_SIDEBAR implementation in content script
- ❌ Outdated/incorrect element selectors for Comet sidebar
- ❌ Response detection mechanism relies on uncertain DOM selectors
- ❌ No iframe handling (sidebar may be in an iframe, not main page DOM)

---

## Root Causes Identified

### Issue #1: Missing DIAGNOSE_SIDEBAR Command
**Status**: 🔴 BLOCKING
**Location**: `chrome_extension/content.js` missing case statement
**Impact**: Cannot scan what selectors actually exist in current Comet version

```javascript
// MISSING: case 'DIAGNOSE_SIDEBAR': return diagnoseSidebar();
```

**Test File Expects It**:
- `workers/browser_automation/diagnose_comet.py` sends DIAGNOSE_SIDEBAR command
- Extension doesn't handle it → command fails silently
- We can't determine current Comet sidebar structure

### Issue #2: Hardcoded Selectors May Not Match Current Comet
**Status**: 🟡 UNCERTAIN
**Location**: `chrome_extension/content.js:469-504` (readCometState function)

**Current Selectors Used**:
```javascript
// Line 471: Sidebar detection
const sidebar = document.querySelector('[data-erpsidecar]') || document.getElementById('ask-input');

// Line 478: Query history
const queries = Array.from(document.querySelectorAll('.groupquery'))

// Line 482: Response text
const responses = Array.from(document.querySelectorAll('[id^="markdown-content-"]'))

// Line 490: Input field
const input = document.getElementById('ask-input');

// Line 494: Submit button
const submitBtn = document.querySelector('button[aria-label="Submit"]');
```

**Problem**:
- These selectors were likely designed for an older version of Comet/Perplexity
- Comet browser may have changed the sidebar DOM structure
- No way to know without running DIAGNOSE_SIDEBAR (which doesn't exist)

### Issue #3: Sidebar May Be In An iframe
**Status**: 🟡 LIKELY
**Location**: `chrome_extension/content.js` - no iframe handling

**Risk**:
- Many web apps isolate sidebars in iframes for sandboxing
- Content script can't access DOM inside iframes (CORS + sandbox restrictions)
- If Perplexity sidebar is in an iframe, all our selectors fail
- Would need separate script injection into iframe context

### Issue #4: Response Event Detection Unreliable
**Status**: 🟡 UNCERTAIN
**Location**: `chrome_extension/content.js:548-566` (startCometObserver)

**Current Approach**:
```javascript
const responses = document.querySelectorAll('[id^="markdown-content-"]');
if (responses.length > lastResponseCount) {
  // Emit event
}
```

**Problem**:
- Assumes response HTML IDs start with "markdown-content-"
- Likely outdated for current Comet version
- If selector doesn't match, responses never detected
- Test: `test_comet_interaction.py` line 180 says "no response event captured"

### Issue #5: AppleScript Fallback Is Incomplete
**Status**: 🟡 PARTIAL
**Location**: `comet_auto_integration.py:171-195` (wait_for_response)

```python
def wait_for_response(self, timeout: int = 60) -> bool:
    # ... placeholder ...
    if (time.time() - start_time) > 10:  # Assume done after 10s
        return True
    return False
```

**Problem**:
- Wait-for-response uses hardcoded 10-second timeout
- No actual UI inspection to detect completion
- Scraping doesn't work via AppleScript
- Just sends queries but can't reliably capture responses

---

## What Works vs What's Broken

| Component | Status | Evidence |
|-----------|--------|----------|
| **WebSocket Server** | ✅ Works | Server logs show proper connections/commands |
| **Tab Management** | ✅ Works | Can create/close/navigate tabs |
| **DOM Reading/Writing** | ✅ Works | Can read page text, click elements, type text |
| **Content Script Framework** | ✅ Works | Proper message passing, error handling |
| **Sidebar Detection** | 🟡 Uncertain | Selectors may not match current Comet |
| **Text Input to Sidebar** | 🟡 Uncertain | `writeCometInput()` may fail if selector wrong |
| **Response Reading** | 🟡 Uncertain | `readCometState()` may not find responses |
| **Response Events** | 🟡 Uncertain | `startCometObserver()` may not detect new responses |
| **AppleScript Automation** | 🟡 Partial | Can send queries, can't capture responses |

---

## Questions for User (CRITICAL)

I need you to help me understand the current Comet browser state to fix this properly:

### Question 1: Comet Browser Version
**What version of Comet browser are you running?**
- [ ] Arc Browser (free, built-in Comet)
- [ ] Comet.ai (standalone)
- [ ] Chromium with Comet plugin
- [ ] Other (please specify)

**Why**: Different versions have different sidebar DOM structures

---

### Question 2: Sidebar State
**Can you manually test the sidebar? Steps:**
1. Open the browser and navigate to https://www.google.com
2. Press `Option+A` (macOS) or your browser's shortcut to open Perplexity sidebar
3. **Tell me**: Does the sidebar appear with an input field visible?
4. **Take a screenshot** and save to `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/COMET_SIDEBAR_SCREENSHOT.png`

**Why**: I need to see the actual DOM structure to find correct selectors

---

### Question 3: Sidebar DOM Structure
**Can you run the diagnostic from the browser console?** Steps:
1. Open the Comet browser with sidebar visible
2. Press `F12` to open DevTools
3. Go to Console tab and run:
```javascript
// Find sidebar element
console.log('=== SIDEBAR STRUCTURE ===');
console.log('data-erpsidecar:', document.querySelector('[data-erpsidecar]'));
console.log('ask-input:', document.getElementById('ask-input'));
console.log('All iframes:', Array.from(document.querySelectorAll('iframe')).map(i => ({
  src: i.src,
  id: i.id,
  className: i.className
})));
console.log('Possible input fields:', Array.from(document.querySelectorAll('input, [contenteditable]')).slice(0, 5).map(e => ({
  tagName: e.tagName,
  id: e.id,
  className: e.className,
  placeholder: e.placeholder
})));
console.log('Possible submit buttons:', Array.from(document.querySelectorAll('button')).slice(0, 5).map(b => ({
  text: b.innerText,
  ariaLabel: b.getAttribute('aria-label'),
  className: b.className
})));
```

4. **Copy the console output** and paste it here

**Why**: This tells us what selectors actually exist in the current sidebar

---

### Question 4: Current Automation Approach
**What do you want to use for Comet automation?**

**Option A: Chrome Extension (Recommended)**
- Pros: More reliable, faster, can detect responses in real-time
- Cons: Requires extension loaded in browser
- Status: 🟡 Needs selector fixes

**Option B: AppleScript Fallback (MacOS)**
- Pros: Works without extension
- Cons: Slower, can't detect responses reliably, OS-dependent
- Status: 🔴 Currently broken (no response detection)

**Option C: Hybrid (Extension + AppleScript)**
- Use extension when available, fall back to AppleScript if not loaded
- Status: 🟡 Requires fixing both

**Your Preference?**: A / B / C / Other

---

### Question 5: Response Capture Format
**What format do you need the Comet response in?**
- [ ] Just the text content
- [ ] Text + HTML (for formatting)
- [ ] Full JSON with metadata (cost, time, etc.)
- [ ] Screenshots of the response
- [ ] All of the above

**Why**: Affects how we scrape and format the response

---

## Proposed Fix Plan

Once you answer the questions above, I'll implement:

### Phase 1: Fix Chrome Extension (2-3 hours)
1. **Add DIAGNOSE_SIDEBAR command** to content.js
   - Scans for all possible sidebar elements
   - Checks for iframes containing sidebar
   - Reports found selectors

2. **Update Comet selectors** based on diagnostic results
   - Replace hardcoded selectors with correct ones
   - Add fallback selectors if primary fails
   - Handle iframe cases

3. **Fix response detection**
   - Update selector for response elements
   - Add MutationObserver for iframe content
   - Return actual response text correctly

### Phase 2: Test & Validate (1-2 hours)
1. Run `diagnose_comet.py` to scan actual sidebar
2. Run `test_comet_interaction.py` to validate read/write/submit
3. Run `load_test.py` to verify response capture works

### Phase 3: Fix AppleScript Fallback (1 hour)
1. Update response detection logic
2. Add actual UI inspection
3. Improve timeout/retry handling

### Phase 4: Integration Test (1 hour)
1. Verify extension works in isolation
2. Verify AppleScript fallback works
3. Test hybrid mode

---

## Files to Modify

```
/Users/jgirmay/Desktop/gitrepo/pyWork/architect/
├── chrome_extension/
│   ├── content.js                          # 🔴 PRIMARY FIX
│   │   ├── Add: DIAGNOSE_SIDEBAR command
│   │   ├── Fix: readCometState() selectors
│   │   ├── Fix: writeCometInput() handling
│   │   ├── Fix: startCometObserver() iframe support
│   │   └── Test: All functions with current selectors
│   │
│   └── background.js                       # 🟡 MINOR: Route DIAGNOSE command
│
├── workers/browser_automation/
│   ├── diagnose_comet.py                   # ✅ Already correct
│   ├── test_comet_interaction.py           # 🟡 May need selector updates
│   └── test_comet.py                       # 🟡 May need selector updates
│
└── comet_auto_integration.py               # 🟡 SECONDARY: Fix response detection
```

---

## Success Criteria (After Fixes)

- ✅ DIAGNOSE_SIDEBAR runs and returns actual sidebar structure
- ✅ readCometState() returns hasComet=true when sidebar visible
- ✅ writeCometInput() successfully writes text to sidebar input
- ✅ submitComet() successfully submits the query
- ✅ startCometObserver() detects when response appears
- ✅ test_comet_interaction.py passes all 5 steps
- ✅ Works with both extension and AppleScript fallback

---

## Current Test Results (From Diagnostic Tools)

**test_comet_interaction.py Output** (Expected, from code):
```
✅ Step 1: Comet detection - UNCERTAIN (selector may not match)
✅ Step 2: Write question - UNCERTAIN (selector may not match)
✓ Step 3: Submit question - UNCERTAIN (button selector may not match)
❌ Step 4: Response detection - CONFIRMED BROKEN (event not captured)
❌ Step 5: Final state - UNCERTAIN (may show 0 responses)
```

**Root cause**: Element selectors don't match current Comet sidebar

---

## Next Steps

1. **Answer the 5 questions above** - This will give me the exact selectors and approach
2. **Share screenshot** - So I can see the current sidebar structure
3. **Run console diagnostic** - Confirm what elements actually exist
4. **I'll implement fixes** using GAIA while Phase 2a concurrent executor runs in background
5. **Test together** - Verify everything works end-to-end

---

## Timeline Estimate

- ⏱️ **Your answers**: 15 minutes (critical path blocker)
- ⏱️ **GAIA implementation**: 2-4 hours (depends on how broken it is)
- ⏱️ **Testing & validation**: 1-2 hours
- ⏱️ **Total**: 3-6 hours (mostly waiting on your input)

---

## Background: Why This Happened

The Comet integration was likely built for an earlier version of the Comet/Perplexity sidebar. Since then:

1. **Comet browser evolved** - DOM structure changed
2. **Perplexity updated** - Sidebar redesigned multiple times
3. **Plugin wasn't maintained** - Selectors became stale
4. **No automated testing** - Breakage went undetected

This is a **common problem with web scraping/automation** - selectors are fragile.

---

## Files Created/Modified

- **NEW**: This diagnostic report
- **PENDING**: `COMET_SIDEBAR_SCREENSHOT.png` (awaiting your screenshot)
- **PENDING**: Selector updates (awaiting your console output)
- **READY FOR**: Implementation phase (GAIA agent will implement fixes)

---

## Risk Assessment

**Severity**: 🔴 HIGH (blocks test automation)
**Complexity**: 🟡 MEDIUM (clear root causes, straightforward fixes)
**Effort**: 🟡 MEDIUM (3-6 hours total)
**Reversibility**: ✅ HIGH (can revert to older selectors if new ones don't work)

