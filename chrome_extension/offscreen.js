/**
 * Architect Browser Agent - Offscreen Document
 * Keeps service worker alive with periodic heartbeat
 */

const HEARTBEAT_INTERVAL = 20000; // 20 seconds

function updateStatus(message) {
  const statusEl = document.getElementById('status');
  if (statusEl) {
    const timestamp = new Date().toLocaleTimeString();
    statusEl.textContent = `${timestamp}: ${message}`;
  }
}

function sendHeartbeat() {
  chrome.runtime.sendMessage({ type: 'heartbeat' }, (response) => {
    if (chrome.runtime.lastError) {
      updateStatus('Disconnected - waiting for background script...');
    } else {
      updateStatus('Connected');
    }
  });
}

// Start heartbeat
setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
sendHeartbeat(); // Initial heartbeat

updateStatus('Offscreen document ready');
console.log('[Architect Offscreen] Keepalive started');
