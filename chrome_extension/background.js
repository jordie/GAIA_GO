/**
 * Architect Browser Agent - Background Service Worker
 * Maintains WebSocket connection to local server and routes commands
 */

// === Configuration ===
// Connect to central server on mac mini via Tailscale
// Tailscale IP: 100.112.58.92 (gezabase.attlocal.net)
// This allows connections from pink laptop, local machine, and other devices
const WS_URL = 'ws://100.112.58.92:8765';
const RECONNECT_DELAY = 3000;
const HEARTBEAT_INTERVAL = 30000;

// === State ===
let ws = null;
let heartbeatTimer = null;
let reconnectTimer = null;
let connected = false;

// === WebSocket Connection Management ===
function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    console.log('[Architect] Already connected');
    return;
  }

  console.log(`[Architect] Connecting to ${WS_URL}...`);
  console.log('[Architect] WebSocket states: CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3');

  try {
    ws = new WebSocket(WS_URL);
  } catch (err) {
    console.error('[Architect] Failed to create WebSocket:', err);
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
    return;
  }

  ws.onopen = () => {
    console.log('[Architect] ✅ Connected to server at', WS_URL);
    console.log('[Architect] WebSocket readyState:', ws.readyState, '(1=OPEN)');
    connected = true;
    clearTimeout(reconnectTimer);

    // Send initial connection event
    send({
      event: 'CONNECTED',
      data: {
        timestamp: Date.now(),
        extensionVersion: chrome.runtime.getManifest().version
      }
    });

    // Report full browser state
    reportFullState();

    // Start heartbeat
    startHeartbeat();
  };

  ws.onmessage = async (event) => {
    try {
      const message = JSON.parse(event.data);

      // Handle ping/pong
      if (message.ping) {
        send({ pong: true, timestamp: Date.now() });
        return;
      }

      // Handle commands
      if (message.command) {
        await executeCommand(message);
      }
    } catch (err) {
      console.error('[Architect] Message handling error:', err);
      send({
        event: 'ERROR',
        data: { message: err.message, stack: err.stack }
      });
    }
  };

  ws.onerror = (error) => {
    console.error('[Architect] WebSocket error:', error);
    console.error('[Architect] Connection state:', ws.readyState);
    console.error('[Architect] Attempting to reconnect in 3s...');
    console.warn('[Architect] Ensure Python server is running: python3 services/browser_ws_server.py');
  };

  ws.onclose = () => {
    console.log('[Architect] Disconnected from server');
    connected = false;
    stopHeartbeat();

    // Auto-reconnect
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
  };
}

function send(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  } else {
    console.warn('[Architect] Cannot send - not connected:', message);
  }
}

function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    send({ heartbeat: true, timestamp: Date.now() });
  }, HEARTBEAT_INTERVAL);
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

// === Browser State Reporting ===
async function reportFullState() {
  try {
    const [groups, tabs, windows] = await Promise.all([
      chrome.tabGroups.query({}),
      chrome.tabs.query({}),
      chrome.windows.getAll()
    ]);

    send({
      event: 'FULL_STATE',
      data: {
        groups: groups.map(g => ({
          id: g.id,
          title: g.title,
          color: g.color,
          collapsed: g.collapsed,
          windowId: g.windowId
        })),
        tabs: tabs.map(t => ({
          id: t.id,
          url: t.url,
          title: t.title,
          groupId: t.groupId,
          active: t.active,
          windowId: t.windowId,
          index: t.index,
          status: t.status
        })),
        windows: windows.map(w => ({
          id: w.id,
          focused: w.focused,
          type: w.type,
          state: w.state
        }))
      }
    });
  } catch (err) {
    console.error('[Architect] Failed to report state:', err);
  }
}

// === Command Execution ===
async function executeCommand(cmd) {
  console.log('[Architect] Executing command:', cmd.action, cmd.id);

  try {
    let result;

    // Route to content script or handle in background
    if (cmd.target === 'content' && cmd.tabId) {
      result = await chrome.tabs.sendMessage(cmd.tabId, cmd);
    } else {
      result = await handleBackgroundCommand(cmd);
    }

    // Send success result
    send({
      event: 'COMMAND_RESULT',
      data: {
        id: cmd.id,
        status: 'success',
        result: result,
        timestamp: Date.now()
      }
    });
  } catch (err) {
    console.error('[Architect] Command failed:', err);

    // Send error result
    send({
      event: 'COMMAND_RESULT',
      data: {
        id: cmd.id,
        status: 'error',
        message: err.message,
        stack: err.stack,
        timestamp: Date.now()
      }
    });
  }
}

async function handleBackgroundCommand(cmd) {
  const { action, params = {} } = cmd;

  switch (action) {
    // Tab operations
    case 'GET_TABS':
      return await chrome.tabs.query(params);

    case 'OPEN_TAB':
      return await chrome.tabs.create(params);

    case 'CLOSE_TAB':
      await chrome.tabs.remove(cmd.tabId);
      return { closed: true };

    case 'NAVIGATE':
      return await chrome.tabs.update(cmd.tabId, { url: params.url });

    case 'ACTIVATE_TAB':
      return await chrome.tabs.update(cmd.tabId, { active: true });

    case 'RELOAD_TAB':
      return await chrome.tabs.reload(cmd.tabId, params);

    // Tab group operations
    case 'GET_TAB_GROUPS':
      return await chrome.tabGroups.query(params);

    case 'CREATE_GROUP': {
      const groupId = await chrome.tabs.group({ tabIds: params.tabIds });
      if (params.title || params.color) {
        await chrome.tabGroups.update(groupId, {
          title: params.title,
          color: params.color
        });
      }
      return { groupId };
    }

    case 'UPDATE_GROUP':
      return await chrome.tabGroups.update(params.groupId, params.props);

    case 'UNGROUP_TABS':
      return await chrome.tabs.ungroup(params.tabIds);

    case 'COLLAPSE_GROUP':
      return await chrome.tabGroups.update(params.groupId, { collapsed: true });

    case 'EXPAND_GROUP':
      return await chrome.tabGroups.update(params.groupId, { collapsed: false });

    // Screenshot
    case 'SCREENSHOT': {
      const dataUrl = await chrome.tabs.captureVisibleTab(null, {
        format: params.format || 'png'
      });
      return { image: dataUrl };
    }

    // Script execution
    case 'EXECUTE_SCRIPT':
      return await chrome.scripting.executeScript({
        target: { tabId: cmd.tabId },
        func: new Function(params.code),
        world: params.world || 'ISOLATED'
      });

    // State reporting
    case 'GET_STATE':
      await reportFullState();
      return { reported: true };

    // Sidebar query - send question to sidebar via content script
    case 'SIDEBAR_QUERY': {
      if (!cmd.tabId) {
        throw new Error('tabId required for SIDEBAR_QUERY');
      }
      const query = params.query || params.question || '';
      if (!query) {
        throw new Error('query or question parameter required');
      }

      // Send to content script to inject into sidebar
      const result = await chrome.tabs.sendMessage(cmd.tabId, {
        action: 'SIDEBAR_QUERY',
        query: query
      });
      return result;
    }

    default:
      throw new Error(`Unknown action: ${action}`);
  }
}

// === Chrome Event Listeners (Push to Server) ===

// Tab events
chrome.tabs.onCreated.addListener((tab) => {
  send({
    event: 'TAB_CREATED',
    data: {
      id: tab.id,
      url: tab.url,
      title: tab.title,
      windowId: tab.windowId,
      index: tab.index
    }
  });
});

chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
  send({
    event: 'TAB_CLOSED',
    data: { tabId, windowId: removeInfo.windowId }
  });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete') {
    send({
      event: 'PAGE_LOADED',
      data: {
        tabId,
        url: tab.url,
        title: tab.title,
        status: tab.status
      }
    });
  }
});

chrome.tabs.onActivated.addListener((activeInfo) => {
  send({
    event: 'TAB_ACTIVATED',
    data: {
      tabId: activeInfo.tabId,
      windowId: activeInfo.windowId
    }
  });
});

// Tab group events
chrome.tabGroups.onCreated.addListener((group) => {
  send({
    event: 'GROUP_CREATED',
    data: {
      id: group.id,
      title: group.title,
      color: group.color,
      windowId: group.windowId
    }
  });
});

chrome.tabGroups.onUpdated.addListener((group) => {
  send({
    event: 'GROUP_UPDATED',
    data: {
      id: group.id,
      title: group.title,
      color: group.color,
      collapsed: group.collapsed
    }
  });
});

chrome.tabGroups.onRemoved.addListener((group) => {
  send({
    event: 'GROUP_REMOVED',
    data: { id: group.id }
  });
});

// Navigation events
chrome.webNavigation.onCompleted.addListener((details) => {
  if (details.frameId === 0) { // Main frame only
    send({
      event: 'NAVIGATION_DONE',
      data: {
        tabId: details.tabId,
        url: details.url,
        timestamp: details.timeStamp
      }
    });
  }
});

// === Message from content scripts ===
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Forward events from content scripts to server
  if (message.event) {
    send({
      event: message.event,
      data: {
        ...message.data,
        tabId: sender.tab?.id,
        url: sender.tab?.url
      }
    });
  }

  sendResponse({ received: true });
  return true;
});

// === Offscreen Document for Service Worker Persistence ===
async function ensureOffscreen() {
  try {
    const contexts = await chrome.runtime.getContexts({
      contextTypes: ['OFFSCREEN_DOCUMENT']
    });

    if (!contexts.length) {
      await chrome.offscreen.createDocument({
        url: 'offscreen.html',
        reasons: ['WORKERS'],
        justification: 'Keep WebSocket connection alive'
      });
      console.log('[Architect] Created offscreen document');
    }
  } catch (err) {
    console.error('[Architect] Failed to create offscreen document:', err);
  }
}

// === Initialization ===
console.log('[Architect] Background service worker starting...');
ensureOffscreen();
connect();

// Keep service worker alive
chrome.runtime.onStartup.addListener(() => {
  console.log('[Architect] Browser started');
  connect();
});

chrome.runtime.onInstalled.addListener((details) => {
  console.log('[Architect] Extension installed/updated:', details.reason);
  connect();
});
