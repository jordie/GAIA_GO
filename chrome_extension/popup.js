/**
 * Architect Browser Agent - Popup
 * Shows connection status and basic stats
 */

const statusEl = document.getElementById('status');
const serverEl = document.getElementById('server');
const tabsEl = document.getElementById('tabs');
const groupsEl = document.getElementById('groups');
const tasksEl = document.getElementById('tasks');
const reconnectBtn = document.getElementById('reconnect');

// Update status display
async function updateStatus() {
  try {
    // Get background service worker status
    const response = await chrome.runtime.sendMessage({ type: 'getStatus' });

    if (response && response.connected) {
      statusEl.className = 'status connected';
      statusEl.textContent = '✓ Connected to Architect Server';
      serverEl.textContent = 'localhost:8765';
    } else {
      statusEl.className = 'status disconnected';
      statusEl.textContent = '✗ Not connected';
      serverEl.textContent = 'Disconnected';
    }

    // Get tab stats
    const tabs = await chrome.tabs.query({});
    const groups = await chrome.tabGroups.query({});

    tabsEl.textContent = tabs.length;
    groupsEl.textContent = groups.length;
    tasksEl.textContent = response?.activeTasks || 0;

  } catch (err) {
    console.error('[Architect Popup] Update failed:', err);
    statusEl.className = 'status disconnected';
    statusEl.textContent = '✗ Error: ' + err.message;
  }
}

// Reconnect button
reconnectBtn.addEventListener('click', async () => {
  reconnectBtn.disabled = true;
  reconnectBtn.textContent = 'Reconnecting...';

  try {
    await chrome.runtime.sendMessage({ type: 'reconnect' });
    setTimeout(() => {
      updateStatus();
      reconnectBtn.disabled = false;
      reconnectBtn.textContent = 'Reconnect';
    }, 2000);
  } catch (err) {
    reconnectBtn.disabled = false;
    reconnectBtn.textContent = 'Reconnect';
  }
});

// Initial update
updateStatus();

// Refresh every 3 seconds
setInterval(updateStatus, 3000);
