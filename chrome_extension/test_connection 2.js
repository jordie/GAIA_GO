/**
 * Diagnostic script for testing WebSocket connection
 *
 * Usage:
 * 1. Open Comet's Developer Tools (F12)
 * 2. Go to Console tab
 * 3. Copy and paste this entire script
 * 4. Check the output
 */

console.log('🔍 Architect Connection Diagnostics\n');

// Test 1: Check if WebSocket is available
console.log('Test 1: WebSocket Support');
if (window.WebSocket) {
  console.log('✅ WebSocket supported');
} else {
  console.log('❌ WebSocket NOT supported');
}

// Test 2: Try to connect to server
console.log('\nTest 2: Connection to ws://localhost:8765');
const ws = new WebSocket('ws://localhost:8765');

ws.onopen = () => {
  console.log('✅ Successfully connected to WebSocket server');
  console.log('   Server is running and accepting connections');

  // Send a test message
  ws.send(JSON.stringify({
    event: 'TEST',
    data: { message: 'Extension test message' }
  }));

  setTimeout(() => ws.close(), 2000);
};

ws.onerror = (error) => {
  console.log('❌ Connection failed');
  console.log('   Error:', error);
  console.log('   Possible causes:');
  console.log('   1. Python server not running (start: python3 services/browser_ws_server.py)');
  console.log('   2. Server not on port 8765');
  console.log('   3. Firewall blocking localhost connections');
  console.log('   4. Browser security restrictions');
};

ws.onmessage = (event) => {
  console.log('📨 Server message received:', event.data);
};

ws.onclose = () => {
  console.log('⚪ Connection closed');
};

// Test 3: Check Comet sidebar
console.log('\nTest 3: Comet Sidebar Detection');
const sidebar = document.querySelector('[data-erpsidecar]') ||
                document.getElementById('ask-input');
if (sidebar) {
  console.log('✅ Comet sidebar found');
  console.log('   Element:', sidebar);
} else {
  console.log('❌ Comet sidebar NOT found');
  console.log('   This page may not have the Comet sidebar');
}

// Test 4: Check if content script is loaded
console.log('\nTest 4: Content Script Status');
if (window.__ARCHITECT_CONTENT_LOADED__) {
  console.log('✅ Architect content script is loaded');
} else {
  console.log('⚠️  Content script may not be loaded');
  console.log('   Extension may not have permissions for this page');
}

// Test 5: Check extension API
console.log('\nTest 5: Extension API Access');
if (chrome && chrome.runtime) {
  console.log('✅ Chrome extension API available');
  console.log('   Can communicate with background script');
} else {
  console.log('❌ Chrome extension API NOT available');
}

console.log('\n🔧 Next Steps:');
console.log('1. Check browser console for errors (above)');
console.log('2. Ensure Python server is running: python3 services/browser_ws_server.py');
console.log('3. Reload the extension (chrome://extensions > refresh)');
console.log('4. Reload this page');
console.log('5. Run this diagnostic again');
