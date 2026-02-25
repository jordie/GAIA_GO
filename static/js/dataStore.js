/**
 * Centralized Data Store with Pub/Sub Pattern
 *
 * This module provides a single source of truth for dashboard data
 * with automatic UI updates via subscriptions.
 *
 * Usage:
 *   DataStore.subscribe('features', (data) => updateFeaturesUI(data));
 *   DataStore.fetch('features');
 *   DataStore.get('features');
 */

const DataStore = (function() {
    'use strict';

    // Internal state
    const state = {
        features: { data: [], loading: false, error: null, lastFetched: null },
        bugs: { data: [], loading: false, error: null, lastFetched: null },
        errors: { data: [], loading: false, error: null, lastFetched: null },
        tasks: { data: [], loading: false, error: null, lastFetched: null },
        workers: { data: null, loading: false, error: null, lastFetched: null },
        nodes: { data: [], loading: false, error: null, lastFetched: null },
        projects: { data: [], loading: false, error: null, lastFetched: null },
        tmuxSessions: { data: [], loading: false, error: null, lastFetched: null },
        stats: { data: null, loading: false, error: null, lastFetched: null }
    };

    // Subscribers for each data type
    const subscribers = {
        features: [],
        bugs: [],
        errors: [],
        tasks: [],
        workers: [],
        nodes: [],
        projects: [],
        tmuxSessions: [],
        stats: [],
        // Special event for any data change (for Quick Access counts)
        '*': []
    };

    // Cache duration in milliseconds (30 seconds default)
    const CACHE_DURATION = 30000;

    // API endpoint mappings
    const endpoints = {
        features: '/features',
        bugs: '/bugs',
        errors: '/errors',
        tasks: '/tasks',
        workers: '/workers/status',
        nodes: '/nodes',
        projects: '/projects',
        tmuxSessions: '/tmux/sessions',
        stats: '/stats'
    };

    /**
     * Subscribe to data changes
     * @param {string} dataType - Type of data to subscribe to (or '*' for all)
     * @param {function} callback - Function to call when data changes
     * @returns {function} Unsubscribe function
     */
    function subscribe(dataType, callback) {
        if (!subscribers[dataType]) {
            console.warn(`DataStore: Unknown data type "${dataType}"`);
            return () => {};
        }
        subscribers[dataType].push(callback);

        // Return unsubscribe function
        return function unsubscribe() {
            const index = subscribers[dataType].indexOf(callback);
            if (index > -1) {
                subscribers[dataType].splice(index, 1);
            }
        };
    }

    /**
     * Notify all subscribers of a data type
     * @param {string} dataType - Type of data that changed
     */
    function notify(dataType) {
        const dataState = state[dataType];

        // Notify specific subscribers
        subscribers[dataType].forEach(callback => {
            try {
                callback(dataState.data, dataState);
            } catch (e) {
                console.error(`DataStore: Error in ${dataType} subscriber:`, e);
            }
        });

        // Notify wildcard subscribers
        subscribers['*'].forEach(callback => {
            try {
                callback(dataType, dataState.data, dataState);
            } catch (e) {
                console.error('DataStore: Error in wildcard subscriber:', e);
            }
        });
    }

    /**
     * Get data synchronously (returns cached data)
     * @param {string} dataType - Type of data to get
     * @returns {any} The cached data
     */
    function get(dataType) {
        if (!state[dataType]) {
            console.warn(`DataStore: Unknown data type "${dataType}"`);
            return null;
        }
        return state[dataType].data;
    }

    /**
     * Get full state including loading/error status
     * @param {string} dataType - Type of data
     * @returns {object} Full state object
     */
    function getState(dataType) {
        return state[dataType] || null;
    }

    /**
     * Check if data is stale and needs refresh
     * @param {string} dataType - Type of data
     * @returns {boolean} True if data is stale
     */
    function isStale(dataType) {
        const dataState = state[dataType];
        if (!dataState || !dataState.lastFetched) return true;
        return Date.now() - dataState.lastFetched > CACHE_DURATION;
    }

    /**
     * Internal API call wrapper
     * @param {string} endpoint - API endpoint
     * @returns {Promise<any>} API response data
     */
    async function apiCall(endpoint) {
        let response;
        try {
            response = await window.fetch(`/api${endpoint}`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin'
            });
        } catch (networkError) {
            throw new Error(`Network error: ${networkError.message || 'unknown'}`);
        }

        if (!response) {
            throw new Error('API error: no response received');
        }

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText || ''}`);
        }

        try {
            const data = await response.json();
            return data !== undefined ? data : null;
        } catch (parseError) {
            throw new Error(`JSON parse error: ${parseError.message || 'invalid response'}`);
        }
    }

    /**
     * Fetch data from API and update store
     * @param {string} dataType - Type of data to fetch
     * @param {object} options - Fetch options
     * @param {boolean} options.force - Force refresh even if cached
     * @param {object} options.params - Query parameters
     * @returns {Promise<any>} The fetched data
     */
    async function fetch(dataType, options = {}) {
        const { force = false, params = {} } = options;

        if (!state[dataType]) {
            console.warn(`DataStore: Unknown data type "${dataType}"`);
            return null;
        }

        // Return cached data if not stale and not forced
        if (!force && !isStale(dataType) && state[dataType].data) {
            return state[dataType].data;
        }

        // Mark as loading
        state[dataType].loading = true;
        state[dataType].error = null;

        try {
            // Build endpoint with query params
            let endpoint = endpoints[dataType];
            const queryParams = new URLSearchParams(params).toString();
            if (queryParams) {
                endpoint += '?' + queryParams;
            }

            const data = await apiCall(endpoint);

            // Normalize data (ensure arrays where expected, handle null/undefined)
            let normalizedData = data;
            if (data == null) {
                // Handle null/undefined response
                normalizedData = ['features', 'bugs', 'tasks', 'nodes', 'projects', 'tmuxSessions', 'errors'].includes(dataType) ? [] : null;
            } else if (dataType === 'errors') {
                normalizedData = Array.isArray(data) ? data :
                    (data && Array.isArray(data.errors) ? data.errors : []);
            } else if (['features', 'bugs', 'tasks', 'nodes', 'projects', 'tmuxSessions'].includes(dataType)) {
                normalizedData = Array.isArray(data) ? data : [];
            }

            // Update state
            state[dataType].data = normalizedData;
            state[dataType].lastFetched = Date.now();
            state[dataType].loading = false;

            // Notify subscribers
            notify(dataType);

            return normalizedData;
        } catch (error) {
            state[dataType].error = error.message;
            state[dataType].loading = false;
            console.error(`DataStore: Error fetching ${dataType}:`, error);
            throw error;
        }
    }

    /**
     * Update local data without fetching (for optimistic updates)
     * @param {string} dataType - Type of data
     * @param {any} data - New data
     */
    function set(dataType, data) {
        if (!state[dataType]) {
            console.warn(`DataStore: Unknown data type "${dataType}"`);
            return;
        }
        state[dataType].data = data;
        state[dataType].lastFetched = Date.now();
        notify(dataType);
    }

    /**
     * Add or update a single item in an array data type
     * @param {string} dataType - Type of data
     * @param {object} item - Item to add/update (must have id)
     */
    function upsertItem(dataType, item) {
        if (!state[dataType] || !Array.isArray(state[dataType].data)) {
            console.warn(`DataStore: Cannot upsert in ${dataType}`);
            return;
        }

        const data = state[dataType].data;
        const index = data.findIndex(d => d.id === item.id);

        if (index > -1) {
            data[index] = { ...data[index], ...item };
        } else {
            data.push(item);
        }

        notify(dataType);
    }

    /**
     * Remove an item from an array data type
     * @param {string} dataType - Type of data
     * @param {number|string} id - ID of item to remove
     */
    function removeItem(dataType, id) {
        if (!state[dataType] || !Array.isArray(state[dataType].data)) {
            console.warn(`DataStore: Cannot remove from ${dataType}`);
            return;
        }

        const index = state[dataType].data.findIndex(d => d.id === id);
        if (index > -1) {
            state[dataType].data.splice(index, 1);
            notify(dataType);
        }
    }

    /**
     * Refresh all data types
     * @param {boolean} force - Force refresh even if cached
     * @returns {Promise<object>} Results object with success/failure counts
     */
    async function refreshAll(force = true) {
        const types = Object.keys(endpoints);
        const results = await Promise.allSettled(types.map(type => fetch(type, { force })));

        // Count successes and failures
        const summary = { success: 0, failed: 0, errors: [] };
        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                summary.success++;
            } else {
                summary.failed++;
                summary.errors.push({ type: types[index], error: result.reason?.message || 'Unknown error' });
            }
        });

        if (summary.failed > 0) {
            console.warn('DataStore: Some fetches failed:', summary.errors);
        }

        return summary;
    }

    /**
     * Get computed counts for Quick Access panel
     * @returns {object} Count summary
     */
    function getCounts() {
        // Safely get arrays with fallback to empty array
        const safeArray = (data) => Array.isArray(data) ? data : [];
        const safeFilter = (arr, predicate) => {
            try {
                return safeArray(arr).filter(item => item && predicate(item)).length;
            } catch (e) {
                return 0;
            }
        };

        const features = safeArray(state.features?.data);
        const bugs = safeArray(state.bugs?.data);
        const errors = safeArray(state.errors?.data);
        const tasks = safeArray(state.tasks?.data);
        const workers = state.workers?.data;
        const nodes = safeArray(state.nodes?.data);

        return {
            features: {
                total: features.length,
                proposed: safeFilter(features, f => f.status === 'proposed'),
                in_progress: safeFilter(features, f => f.status === 'in_progress'),
                completed: safeFilter(features, f => f.status === 'completed')
            },
            bugs: {
                total: bugs.length,
                open: safeFilter(bugs, b => b.status === 'open'),
                in_progress: safeFilter(bugs, b => b.status === 'in_progress'),
                resolved: safeFilter(bugs, b => b.status === 'resolved'),
                critical: safeFilter(bugs, b => b.severity === 'critical')
            },
            errors: {
                total: errors.length,
                open: safeFilter(errors, e => e.status === 'open'),
                resolved: safeFilter(errors, e => e.status === 'resolved')
            },
            tasks: {
                total: tasks.length,
                pending: safeFilter(tasks, t => t.status === 'pending'),
                in_progress: safeFilter(tasks, t => t.status === 'in_progress'),
                completed: safeFilter(tasks, t => t.status === 'completed')
            },
            workers: {
                total: workers?.stats?.total ?? 0,
                active: workers?.stats?.active ?? 0,
                idle: workers?.stats?.idle ?? 0,
                offline: workers?.stats?.offline ?? 0
            },
            nodes: {
                total: nodes.length,
                online: safeFilter(nodes, n => n.status === 'online'),
                offline: safeFilter(nodes, n => n.status === 'offline')
            }
        };
    }

    /**
     * Invalidate cache for a data type
     * @param {string} dataType - Type of data to invalidate
     */
    function invalidate(dataType) {
        if (state[dataType]) {
            state[dataType].lastFetched = null;
        }
    }

    /**
     * Clear all cached data
     */
    function clearAll() {
        Object.keys(state).forEach(key => {
            state[key].data = Array.isArray(state[key].data) ? [] : null;
            state[key].lastFetched = null;
            state[key].error = null;
        });
    }

    // Public API
    return {
        subscribe,
        get,
        getState,
        isStale,
        fetch,
        set,
        upsertItem,
        removeItem,
        refreshAll,
        getCounts,
        invalidate,
        clearAll
    };
})();

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DataStore;
}
