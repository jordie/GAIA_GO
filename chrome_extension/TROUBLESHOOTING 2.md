# Architect Extension Troubleshooting Guide

## WebSocket Connection Error

**Error message:** `WebSocket error: Event { type: 'error', ... }`

This means the extension cannot connect to the Python backend server.

### Quick Checklist

- [ ] Is the Python WebSocket server running?
- [ ] Is it running on port 8765?
- [ ] Can you access localhost:8765 from Comet?
- [ ] No firewall blocking localhost?
- [ ] Extension properly loaded?

---

## Step-by-Step Diagnostic

### 1. Start the Python Server

```bash
# Navigate to architect directory
cd /Users/jgirmay/Desktop/gitrepo/pyWork/architect

# Start the WebSocket server
python3 services/browser_ws_server.py
```

**Expected output:**
```
Starting Architect Browser Agent WebSocket server on localhost:8765
✓ Server listening on ws://localhost:8765
Waiting for Chrome extension to connect...
```

If you don't see this, check:
- Python 3 is installed: `python3 --version`
- websockets library is installed: `pip3 list | grep websockets`
- Port 8765 is not in use: `lsof -i :8765`

### 2. Verify Server is Listening

```bash
# Check if server is listening on port 8765
lsof -i :8765

# Should show something like:
# COMMAND    PID   USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
# python3   1234   user   3u  IPv4 0x12345678      0t0  TCP localhost:8765 (LISTEN)
```

### 3. Test from Browser Console

1. **Open Comet browser**
2. **Open Developer Tools**: F12 or Cmd+Option+I
3. **Go to Console tab**
4. **Paste and run this code:**

```javascript
// Test WebSocket connection
const ws = new WebSocket('ws://localhost:8765');

ws.onopen = () => {
  console.log('✅ WebSocket Connected!');
  console.log('Server is running and accessible');
};

ws.onerror = (err) => {
  console.log('❌ WebSocket Failed');
  console.log('Error:', err);
  console.log('Check if Python server is running on localhost:8765');
};

ws.onmessage = (msg) => {
  console.log('Message from server:', msg.data);
};

// Clean up after 5 seconds
setTimeout(() => {
  if (ws) ws.close();
}, 5000);
```

**If it says "✅ WebSocket Connected!"**
- Server is running and accessible
- Problem is likely in the extension setup

**If it says "❌ WebSocket Failed"**
- Server is not running or not accessible
- Start the server (step 1 above)

### 4. Check Extension Connection

1. **Open Extension Console**
   - Comet → Settings → Extensions
   - Find "Architect Browser Agent"
   - Click "Details"
   - Click "Background" or "Service Worker"

2. **Look for these messages:**
   ```
   [Architect] Connecting to ws://localhost:8765...
   [Architect] ✅ Connected to server at ws://localhost:8765
   ```

3. **If you see errors:**
   ```
   [Architect] WebSocket error: Event {...}
   [Architect] Attempting to reconnect in 3s...
   ```
   → Server is not accessible. Check steps 1-3 above.

### 5. Reload Extension and Page

```
1. Go to chrome://extensions/ (or settings in Comet)
2. Find "Architect Browser Agent"
3. Click the Refresh button
4. Reload the page you're testing
5. Check the extension console again
```

---

## Common Issues & Solutions

### Issue: "Connection refused" or "ERR_CONNECTION_REFUSED"

**Cause:** Server not running on port 8765

**Solution:**
```bash
python3 services/browser_ws_server.py
```

Then reload the extension and page.

---

### Issue: "net::ERR_INVALID_ARGUMENT"

**Cause:** WebSocket URL is malformed

**Check:** In background.js, line 7:
```javascript
const WS_URL = 'ws://localhost:8765';
```

Should be exactly: `ws://localhost:8765` (not `http://`, not `wss://`)

---

### Issue: Connection works in console but not in extension

**Cause:** Content script not loaded or extension not properly injected

**Solution:**
1. Check manifest.json has correct content_scripts
2. Verify extension has permission for the page
3. Try on a new tab
4. Reload extension and page

---

### Issue: Comet sidebar not detected

**Cause:** Comet's DOM structure may have changed

**Elements to check in console:**
```javascript
// Check for sidebar
document.querySelector('[data-erpsidecar]')  // Element or null

// Check for input
document.getElementById('ask-input')          // Element or null

// Check for submit button
document.querySelector('button[aria-label="Submit"]')  // Element or null
```

If these return `null`, the sidebar may have different selectors. Report this!

---

## Testing Comet Integration

Once the WebSocket connection works, test Comet interaction:

```javascript
// In browser console on a page with Comet sidebar

// 1. Read current state
chrome.runtime.sendMessage({
  action: 'READ_COMET',
  target: 'content'
}, (response) => {
  console.log('Comet state:', response);
});

// 2. Write to input
chrome.runtime.sendMessage({
  action: 'WRITE_COMET',
  target: 'content',
  params: { text: 'Test query' }
}, (response) => {
  console.log('Write result:', response);
});

// 3. Submit
chrome.runtime.sendMessage({
  action: 'SUBMIT_COMET',
  target: 'content'
}, (response) => {
  console.log('Submit result:', response);
});
```

---

## Debug Mode

Enable more verbose logging by adding this to background.js:

```javascript
// Add at top of file
const DEBUG = true;

// Wrap all console.log calls:
const log = (msg) => DEBUG && console.log(msg);
const error = (msg) => console.error(msg);
```

---

## Need Help?

1. **Check the logs:**
   - Extension service worker console (chrome://extensions)
   - Python server terminal output
   - Browser console (F12)

2. **Check the files:**
   - Server running: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/services/browser_ws_server.py`
   - Manifest: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/chrome_extension/manifest.json`
   - Background: `/Users/jgirmay/Desktop/gitrepo/pyWork/architect/chrome_extension/background.js`

3. **Try the diagnostic script:**
   Copy and run `test_connection.js` in Comet's console

4. **Restart everything:**
   ```bash
   # Kill server (Ctrl+C in terminal)
   # Reload extension (F5 on extensions page)
   # Reload web page (F5)
   # Start server again
   python3 services/browser_ws_server.py
   ```
