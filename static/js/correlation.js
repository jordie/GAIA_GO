/**
 * Correlation ID Module
 *
 * Handles correlation IDs for request tracing on the frontend.
 *
 * Features:
 * - Extract correlation ID from response headers
 * - Display correlation ID in error messages
 * - Include correlation ID in support tickets
 * - Log correlation IDs for debugging
 *
 * Usage:
 *   // Get current correlation ID
 *   const id = Correlation.getId();
 *
 *   // Include in error reports
 *   Correlation.formatError(error);
 */

const Correlation = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        headerName: 'X-Correlation-ID',
        storageKey: 'last_correlation_id',
        maxStoredIds: 10
    };

    // Store recent correlation IDs for debugging
    let recentIds = [];

    /**
     * Initialize correlation ID tracking.
     */
    function init() {
        // Intercept fetch to capture correlation IDs from responses
        patchFetch();
        console.log('[Correlation] Tracking initialized');
    }

    /**
     * Get the current/last correlation ID.
     *
     * @returns {string|null} The correlation ID
     */
    function getId() {
        return recentIds.length > 0 ? recentIds[recentIds.length - 1] : null;
    }

    /**
     * Get all recent correlation IDs.
     *
     * @returns {Array<string>} Array of recent correlation IDs
     */
    function getRecentIds() {
        return [...recentIds];
    }

    /**
     * Store a correlation ID.
     *
     * @param {string} id - The correlation ID to store
     */
    function storeId(id) {
        if (!id) return;

        // Add to recent list
        recentIds.push(id);

        // Keep only recent IDs
        if (recentIds.length > CONFIG.maxStoredIds) {
            recentIds.shift();
        }

        // Store in session storage for persistence across page loads
        try {
            sessionStorage.setItem(CONFIG.storageKey, id);
        } catch (e) {
            // Session storage may be unavailable
        }
    }

    /**
     * Extract correlation ID from fetch response.
     *
     * @param {Response} response - Fetch response
     * @returns {string|null} The correlation ID
     */
    function extractFromResponse(response) {
        const id = response.headers.get(CONFIG.headerName);
        if (id) {
            storeId(id);
        }
        return id;
    }

    /**
     * Patch fetch to capture correlation IDs.
     */
    function patchFetch() {
        const originalFetch = window.fetch;

        window.fetch = async function(...args) {
            const response = await originalFetch.apply(this, args);

            // Extract correlation ID from response
            extractFromResponse(response);

            return response;
        };
    }

    /**
     * Format an error message with correlation ID.
     *
     * @param {Error|Object} error - The error object
     * @param {string} [correlationId] - Optional specific correlation ID
     * @returns {string} Formatted error message
     */
    function formatError(error, correlationId = null) {
        const id = correlationId || getId();
        const message = error.message || error.error || String(error);

        if (id) {
            return `${message} (Request ID: ${id})`;
        }
        return message;
    }

    /**
     * Get error context for support/debugging.
     *
     * @param {Error|Object} error - The error object
     * @returns {Object} Error context with correlation info
     */
    function getErrorContext(error) {
        return {
            message: error.message || error.error || String(error),
            correlation_id: getId(),
            recent_ids: getRecentIds(),
            timestamp: new Date().toISOString(),
            url: window.location.href,
            user_agent: navigator.userAgent
        };
    }

    /**
     * Copy correlation ID to clipboard.
     *
     * @param {string} [id] - Optional specific ID to copy
     * @returns {Promise<boolean>} Success status
     */
    async function copyToClipboard(id = null) {
        const correlationId = id || getId();
        if (!correlationId) {
            console.warn('[Correlation] No correlation ID to copy');
            return false;
        }

        try {
            await navigator.clipboard.writeText(correlationId);
            console.log('[Correlation] Copied to clipboard:', correlationId);
            return true;
        } catch (e) {
            console.error('[Correlation] Failed to copy:', e);
            return false;
        }
    }

    /**
     * Create a support reference string.
     *
     * @returns {string} Support reference
     */
    function getSupportReference() {
        const id = getId();
        if (!id) {
            return 'No request ID available';
        }
        return `Request ID: ${id}`;
    }

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    return {
        init,
        getId,
        getRecentIds,
        storeId,
        extractFromResponse,
        formatError,
        getErrorContext,
        copyToClipboard,
        getSupportReference,
        CONFIG
    };
})();

// Expose globally
window.Correlation = Correlation;
