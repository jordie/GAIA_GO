/**
 * Dashboard Refresh Manager
 *
 * Provides seamless data refresh without page reload with:
 * - Visual loading indicators
 * - Configurable refresh intervals
 * - Per-panel refresh capability
 * - Progress tracking
 * - Error handling with retry
 */

const DashboardRefresh = (function() {
    'use strict';

    // Configuration
    const config = {
        defaultInterval: 30000,  // 30 seconds
        minInterval: 5000,       // 5 seconds minimum
        maxInterval: 300000,     // 5 minutes maximum
        retryAttempts: 3,
        retryDelay: 2000,
        showNotifications: true
    };

    // State
    const state = {
        isRefreshing: false,
        autoRefreshEnabled: false,
        autoRefreshInterval: null,
        currentInterval: config.defaultInterval,
        lastRefreshTime: null,
        refreshCount: 0,
        errorCount: 0,
        pendingRefreshes: new Set(),
        panelRefreshCallbacks: {}
    };

    // Available refresh intervals
    const INTERVALS = [
        { value: 5000, label: '5s' },
        { value: 10000, label: '10s' },
        { value: 15000, label: '15s' },
        { value: 30000, label: '30s' },
        { value: 60000, label: '1m' },
        { value: 120000, label: '2m' },
        { value: 300000, label: '5m' }
    ];

    // Data sources to refresh
    const DATA_SOURCES = [
        { id: 'projects', endpoint: '/api/projects', priority: 1 },
        { id: 'features', endpoint: '/api/features', priority: 2 },
        { id: 'bugs', endpoint: '/api/bugs', priority: 2 },
        { id: 'tasks', endpoint: '/api/tasks', priority: 2 },
        { id: 'errors', endpoint: '/api/errors', priority: 3 },
        { id: 'workers', endpoint: '/api/workers/status', priority: 3 },
        { id: 'nodes', endpoint: '/api/nodes', priority: 3 },
        { id: 'stats', endpoint: '/api/stats', priority: 1 },
        { id: 'tmux', endpoint: '/api/tmux/sessions', priority: 4 }
    ];

    /**
     * Initialize the refresh manager
     */
    function init() {
        // Load saved preferences
        loadPreferences();

        // Create refresh indicator UI
        createRefreshIndicator();

        // Set up keyboard shortcuts
        setupKeyboardShortcuts();

        // Restore auto-refresh state
        if (state.autoRefreshEnabled) {
            startAutoRefresh();
        }

        // Listen for visibility changes to pause/resume auto-refresh
        document.addEventListener('visibilitychange', handleVisibilityChange);

        console.log('[DashboardRefresh] Initialized');
    }

    /**
     * Load saved preferences from localStorage
     */
    function loadPreferences() {
        try {
            const saved = localStorage.getItem('dashboardRefreshPrefs');
            if (saved) {
                const prefs = JSON.parse(saved);
                state.autoRefreshEnabled = prefs.autoRefreshEnabled || false;
                state.currentInterval = prefs.interval || config.defaultInterval;
                config.showNotifications = prefs.showNotifications !== false;
            }
        } catch (e) {
            console.warn('[DashboardRefresh] Error loading preferences:', e);
        }
    }

    /**
     * Save preferences to localStorage
     */
    function savePreferences() {
        try {
            localStorage.setItem('dashboardRefreshPrefs', JSON.stringify({
                autoRefreshEnabled: state.autoRefreshEnabled,
                interval: state.currentInterval,
                showNotifications: config.showNotifications
            }));
        } catch (e) {
            console.warn('[DashboardRefresh] Error saving preferences:', e);
        }
    }

    /**
     * Create the refresh indicator UI element
     */
    function createRefreshIndicator() {
        // Check if indicator already exists
        if (document.getElementById('refreshIndicator')) return;

        const indicator = document.createElement('div');
        indicator.id = 'refreshIndicator';
        indicator.className = 'refresh-indicator';
        indicator.innerHTML = `
            <div class="refresh-indicator-content">
                <div class="refresh-spinner"></div>
                <span class="refresh-text">Refreshing...</span>
                <div class="refresh-progress">
                    <div class="refresh-progress-bar"></div>
                </div>
            </div>
        `;
        document.body.appendChild(indicator);

        // Add styles if not already present
        if (!document.getElementById('refreshIndicatorStyles')) {
            const style = document.createElement('style');
            style.id = 'refreshIndicatorStyles';
            style.textContent = `
                .refresh-indicator {
                    position: fixed;
                    top: 60px;
                    right: 20px;
                    background: var(--bg-secondary, #161b22);
                    border: 1px solid var(--border, #30363d);
                    border-radius: 8px;
                    padding: 12px 16px;
                    display: none;
                    align-items: center;
                    gap: 12px;
                    z-index: 10000;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    animation: slideIn 0.2s ease-out;
                }
                .refresh-indicator.active {
                    display: flex;
                }
                .refresh-indicator-content {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .refresh-spinner {
                    width: 16px;
                    height: 16px;
                    border: 2px solid var(--border, #30363d);
                    border-top-color: var(--accent, #58a6ff);
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }
                .refresh-text {
                    font-size: 13px;
                    color: var(--text-secondary, #8b949e);
                }
                .refresh-progress {
                    width: 60px;
                    height: 4px;
                    background: var(--bg-tertiary, #21262d);
                    border-radius: 2px;
                    overflow: hidden;
                }
                .refresh-progress-bar {
                    height: 100%;
                    width: 0%;
                    background: var(--accent, #58a6ff);
                    border-radius: 2px;
                    transition: width 0.3s ease;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                @keyframes slideIn {
                    from { transform: translateX(100px); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }

                /* Panel refresh overlay */
                .panel-refreshing {
                    position: relative;
                }
                .panel-refreshing::after {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0,0,0,0.1);
                    pointer-events: none;
                    animation: pulse 1s ease-in-out infinite;
                }
                @keyframes pulse {
                    0%, 100% { opacity: 0.3; }
                    50% { opacity: 0.1; }
                }

                /* Refresh button states */
                .btn-refresh.refreshing {
                    pointer-events: none;
                    opacity: 0.7;
                }
                .btn-refresh.refreshing .btn-icon {
                    animation: spin 0.8s linear infinite;
                }

                /* Auto-refresh countdown */
                .auto-refresh-countdown {
                    font-size: 11px;
                    color: var(--text-secondary, #8b949e);
                    margin-left: 8px;
                }

                /* Refresh interval selector */
                .refresh-interval-selector {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 12px;
                }
                .refresh-interval-selector select {
                    background: var(--bg-tertiary, #21262d);
                    border: 1px solid var(--border, #30363d);
                    color: var(--text-primary, #f0f6fc);
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 12px;
                    cursor: pointer;
                }
            `;
            document.head.appendChild(style);
        }
    }

    /**
     * Set up keyboard shortcuts
     */
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + R for manual refresh (prevent default browser reload)
            if ((e.ctrlKey || e.metaKey) && e.key === 'r' && !e.shiftKey) {
                e.preventDefault();
                refreshAll();
            }
            // F5 for refresh
            if (e.key === 'F5' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                refreshAll();
            }
        });
    }

    /**
     * Handle page visibility changes
     */
    function handleVisibilityChange() {
        if (document.hidden) {
            // Page is hidden, pause auto-refresh
            if (state.autoRefreshInterval) {
                clearInterval(state.autoRefreshInterval);
                state.autoRefreshInterval = null;
            }
        } else {
            // Page is visible again
            if (state.autoRefreshEnabled && !state.autoRefreshInterval) {
                // Trigger immediate refresh when returning
                refreshAll();
                startAutoRefresh();
            }
        }
    }

    /**
     * Show the refresh indicator
     */
    function showIndicator(text = 'Refreshing...') {
        const indicator = document.getElementById('refreshIndicator');
        if (indicator) {
            indicator.querySelector('.refresh-text').textContent = text;
            indicator.classList.add('active');
        }
    }

    /**
     * Hide the refresh indicator
     */
    function hideIndicator() {
        const indicator = document.getElementById('refreshIndicator');
        if (indicator) {
            indicator.classList.remove('active');
        }
    }

    /**
     * Update progress bar
     */
    function updateProgress(percent) {
        const progressBar = document.querySelector('.refresh-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${percent}%`;
        }
    }

    /**
     * Refresh all dashboard data
     */
    async function refreshAll(options = {}) {
        const { silent = false, force = true } = options;

        if (state.isRefreshing) {
            console.log('[DashboardRefresh] Refresh already in progress');
            return { success: false, reason: 'already_refreshing' };
        }

        state.isRefreshing = true;
        state.refreshCount++;

        if (!silent) {
            showIndicator('Refreshing data...');
        }

        const startTime = Date.now();
        const results = { success: [], failed: [], duration: 0 };

        try {
            // Sort by priority
            const sources = [...DATA_SOURCES].sort((a, b) => a.priority - b.priority);
            const total = sources.length;
            let completed = 0;

            // Use DataStore if available, otherwise fetch directly
            if (typeof DataStore !== 'undefined') {
                const fetchPromises = sources.map(async (source) => {
                    try {
                        // Map source id to DataStore keys
                        const dataStoreKey = source.id === 'tmux' ? 'tmuxSessions' : source.id;
                        await DataStore.fetch(dataStoreKey, { force });
                        results.success.push(source.id);
                    } catch (error) {
                        results.failed.push({ id: source.id, error: error.message });
                    } finally {
                        completed++;
                        updateProgress((completed / total) * 100);
                    }
                });

                await Promise.allSettled(fetchPromises);
            } else {
                // Fallback to direct API calls
                for (const source of sources) {
                    try {
                        const response = await fetch(source.endpoint, {
                            credentials: 'same-origin',
                            headers: { 'Content-Type': 'application/json' }
                        });
                        if (response.ok) {
                            results.success.push(source.id);
                        } else {
                            results.failed.push({ id: source.id, error: `HTTP ${response.status}` });
                        }
                    } catch (error) {
                        results.failed.push({ id: source.id, error: error.message });
                    }
                    completed++;
                    updateProgress((completed / total) * 100);
                }
            }

            // Call panel-specific refresh callbacks
            await refreshPanels();

            // Update UI elements
            updateRefreshTime();
            updateProgress(100);

            results.duration = Date.now() - startTime;
            state.lastRefreshTime = new Date();
            state.errorCount = results.failed.length;

            // Show notification if there were errors
            if (results.failed.length > 0 && config.showNotifications && !silent) {
                showRefreshNotification('warning',
                    `Refresh completed with ${results.failed.length} error(s)`);
            }

            // Emit refresh event
            emitRefreshEvent(results);

            return { success: true, results };

        } catch (error) {
            console.error('[DashboardRefresh] Error during refresh:', error);
            if (config.showNotifications && !silent) {
                showRefreshNotification('error', 'Refresh failed: ' + error.message);
            }
            return { success: false, error: error.message };

        } finally {
            state.isRefreshing = false;
            setTimeout(() => {
                hideIndicator();
                updateProgress(0);
            }, 500);
        }
    }

    /**
     * Refresh a specific panel
     */
    async function refreshPanel(panelId) {
        if (state.pendingRefreshes.has(panelId)) {
            return { success: false, reason: 'already_refreshing' };
        }

        state.pendingRefreshes.add(panelId);

        // Add visual feedback
        const panelEl = document.getElementById(panelId) ||
                        document.querySelector(`[data-panel="${panelId}"]`);
        if (panelEl) {
            panelEl.classList.add('panel-refreshing');
        }

        try {
            // Call registered callback
            if (state.panelRefreshCallbacks[panelId]) {
                await state.panelRefreshCallbacks[panelId]();
            }

            // Also refresh related data in DataStore
            const panelDataMap = {
                'overview': ['stats', 'projects'],
                'features': ['features'],
                'bugs': ['bugs'],
                'errors': ['errors'],
                'tasks': ['tasks'],
                'queue': ['tasks'],
                'workers': ['workers'],
                'nodes': ['nodes'],
                'tmux': ['tmuxSessions'],
                'projects': ['projects']
            };

            const dataKeys = panelDataMap[panelId] || [];
            if (typeof DataStore !== 'undefined') {
                await Promise.all(dataKeys.map(key => DataStore.fetch(key, { force: true })));
            }

            return { success: true };

        } catch (error) {
            console.error(`[DashboardRefresh] Error refreshing panel ${panelId}:`, error);
            return { success: false, error: error.message };

        } finally {
            state.pendingRefreshes.delete(panelId);
            if (panelEl) {
                panelEl.classList.remove('panel-refreshing');
            }
        }
    }

    /**
     * Register a panel refresh callback
     */
    function registerPanelRefresh(panelId, callback) {
        state.panelRefreshCallbacks[panelId] = callback;
    }

    /**
     * Refresh all registered panels
     */
    async function refreshPanels() {
        const promises = Object.entries(state.panelRefreshCallbacks).map(
            async ([panelId, callback]) => {
                try {
                    await callback();
                } catch (error) {
                    console.warn(`[DashboardRefresh] Panel ${panelId} refresh error:`, error);
                }
            }
        );
        await Promise.allSettled(promises);
    }

    /**
     * Start auto-refresh
     */
    function startAutoRefresh(interval = null) {
        if (interval !== null) {
            state.currentInterval = Math.max(config.minInterval,
                Math.min(interval, config.maxInterval));
        }

        stopAutoRefresh();

        state.autoRefreshEnabled = true;
        state.autoRefreshInterval = setInterval(() => {
            refreshAll({ silent: true });
        }, state.currentInterval);

        savePreferences();
        updateAutoRefreshUI();

        console.log(`[DashboardRefresh] Auto-refresh started (${state.currentInterval}ms)`);
    }

    /**
     * Stop auto-refresh
     */
    function stopAutoRefresh() {
        if (state.autoRefreshInterval) {
            clearInterval(state.autoRefreshInterval);
            state.autoRefreshInterval = null;
        }
        state.autoRefreshEnabled = false;
        savePreferences();
        updateAutoRefreshUI();

        console.log('[DashboardRefresh] Auto-refresh stopped');
    }

    /**
     * Toggle auto-refresh
     */
    function toggleAutoRefresh(enabled = null) {
        if (enabled === null) {
            enabled = !state.autoRefreshEnabled;
        }

        if (enabled) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }

        return state.autoRefreshEnabled;
    }

    /**
     * Set refresh interval
     */
    function setInterval(ms) {
        const interval = Math.max(config.minInterval, Math.min(ms, config.maxInterval));
        state.currentInterval = interval;

        if (state.autoRefreshEnabled) {
            startAutoRefresh(interval);
        } else {
            savePreferences();
        }

        return interval;
    }

    /**
     * Update auto-refresh UI elements
     */
    function updateAutoRefreshUI() {
        // Update toggle checkboxes
        document.querySelectorAll('[data-auto-refresh-toggle], #autoRefreshToggle').forEach(el => {
            if (el.type === 'checkbox') {
                el.checked = state.autoRefreshEnabled;
            }
        });

        // Update status text
        const statusEl = document.getElementById('autoRefreshStatus');
        if (statusEl) {
            statusEl.textContent = state.autoRefreshEnabled ? 'On' : 'Off';
        }

        // Update interval selectors
        document.querySelectorAll('[data-refresh-interval]').forEach(el => {
            el.value = state.currentInterval;
        });
    }

    /**
     * Update the last refresh time display
     */
    function updateRefreshTime() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();

        // Update all refresh time elements
        document.querySelectorAll('#lastRefreshTime, [data-last-refresh]').forEach(el => {
            el.textContent = `Updated ${timeStr}`;
        });

        // Update overview refresh display
        const overviewRefresh = document.getElementById('overviewLastRefresh');
        if (overviewRefresh) {
            overviewRefresh.textContent = timeStr;
        }
    }

    /**
     * Show a refresh notification
     */
    function showRefreshNotification(type, message) {
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            console.log(`[DashboardRefresh] ${type}: ${message}`);
        }
    }

    /**
     * Emit a custom refresh event
     */
    function emitRefreshEvent(results) {
        const event = new CustomEvent('dashboardRefresh', {
            detail: {
                timestamp: new Date().toISOString(),
                results,
                refreshCount: state.refreshCount
            }
        });
        document.dispatchEvent(event);
    }

    /**
     * Get current state
     */
    function getState() {
        return {
            isRefreshing: state.isRefreshing,
            autoRefreshEnabled: state.autoRefreshEnabled,
            currentInterval: state.currentInterval,
            lastRefreshTime: state.lastRefreshTime,
            refreshCount: state.refreshCount,
            errorCount: state.errorCount
        };
    }

    /**
     * Get available intervals
     */
    function getIntervals() {
        return [...INTERVALS];
    }

    /**
     * Create refresh controls HTML
     */
    function createRefreshControls(options = {}) {
        const { showInterval = true, showCountdown = false, compact = false } = options;

        const intervalOptions = INTERVALS.map(i =>
            `<option value="${i.value}" ${i.value === state.currentInterval ? 'selected' : ''}>
                ${i.label}
            </option>`
        ).join('');

        if (compact) {
            return `
                <div class="refresh-controls-compact" style="display: flex; align-items: center; gap: 8px;">
                    <button class="btn btn-secondary btn-sm" onclick="DashboardRefresh.refreshAll()"
                            title="Refresh now (Ctrl+R)">
                        <span class="btn-icon">↻</span>
                    </button>
                    <label class="auto-refresh-toggle" title="Auto-refresh">
                        <input type="checkbox" data-auto-refresh-toggle
                               ${state.autoRefreshEnabled ? 'checked' : ''}
                               onchange="DashboardRefresh.toggleAutoRefresh(this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            `;
        }

        return `
            <div class="refresh-controls" style="display: flex; align-items: center; gap: 12px;">
                <span id="lastRefreshTime" data-last-refresh
                      style="font-size: 12px; color: var(--text-secondary);">
                    ${state.lastRefreshTime ? 'Updated ' + state.lastRefreshTime.toLocaleTimeString() : 'Not refreshed yet'}
                </span>
                ${showInterval ? `
                    <div class="refresh-interval-selector">
                        <select data-refresh-interval onchange="DashboardRefresh.setInterval(parseInt(this.value))">
                            ${intervalOptions}
                        </select>
                    </div>
                ` : ''}
                <label class="auto-refresh-toggle" title="Auto-refresh">
                    <input type="checkbox" data-auto-refresh-toggle
                           ${state.autoRefreshEnabled ? 'checked' : ''}
                           onchange="DashboardRefresh.toggleAutoRefresh(this.checked)">
                    <span class="toggle-slider"></span>
                    <span style="font-size: 12px; margin-left: 4px;">Auto</span>
                </label>
                ${showCountdown ? '<span class="auto-refresh-countdown" data-countdown></span>' : ''}
                <button class="btn btn-primary" onclick="DashboardRefresh.refreshAll()"
                        title="Refresh now (Ctrl+R)">
                    Refresh
                </button>
            </div>
        `;
    }

    // Public API
    return {
        init,
        refreshAll,
        refreshPanel,
        registerPanelRefresh,
        startAutoRefresh,
        stopAutoRefresh,
        toggleAutoRefresh,
        setInterval,
        getState,
        getIntervals,
        createRefreshControls
    };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => DashboardRefresh.init());
} else {
    DashboardRefresh.init();
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DashboardRefresh;
}
