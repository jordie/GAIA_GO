/**
 * CSRF Protection Module
 *
 * Provides Cross-Site Request Forgery protection for all frontend requests.
 *
 * Features:
 * - Automatic CSRF token injection into all AJAX requests
 * - Token refresh before expiration
 * - Form protection helpers
 * - Cookie-based token retrieval (double-submit pattern)
 *
 * Usage:
 *   // Automatic: All fetch requests through api() include CSRF token
 *
 *   // Manual for custom requests:
 *   CSRF.getToken()                    // Get current token
 *   CSRF.addToHeaders(headers)         // Add token to headers object
 *   CSRF.addToForm(formElement)        // Add hidden input to form
 *   CSRF.refresh()                     // Force token refresh
 */

const CSRF = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        headerName: 'X-CSRF-Token',
        formFieldName: 'csrf_token',
        cookieName: 'csrf_double_submit',
        refreshEndpoint: '/api/csrf/token',
        tokenLifetime: 3600000,  // 1 hour in milliseconds
        refreshThreshold: 300000  // Refresh when 5 minutes remaining
    };

    // Internal state
    let _token = null;
    let _tokenTime = null;
    let _refreshTimer = null;
    let _pendingRefresh = null;

    /**
     * Initialize CSRF protection.
     * Extracts token from page meta tag or cookie.
     */
    function init() {
        // Try to get token from meta tag (set by server)
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            _token = metaTag.getAttribute('content');
            _tokenTime = Date.now();
        }

        // Try cookie as fallback
        if (!_token) {
            _token = getCookie(CONFIG.cookieName);
            if (_token) {
                _tokenTime = Date.now();
            }
        }

        // Set up automatic refresh timer
        scheduleRefresh();

        // Intercept native fetch for automatic CSRF
        patchFetch();

        console.log('[CSRF] Protection initialized');
    }

    /**
     * Get the current CSRF token.
     * Refreshes if token is about to expire.
     *
     * @returns {string|null} The CSRF token
     */
    function getToken() {
        // Check if token needs refresh
        if (shouldRefresh()) {
            refresh();  // Non-blocking refresh
        }
        return _token;
    }

    /**
     * Set the CSRF token (called when received from server).
     *
     * @param {string} token - The new CSRF token
     */
    function setToken(token) {
        _token = token;
        _tokenTime = Date.now();
        scheduleRefresh();
    }

    /**
     * Check if token should be refreshed.
     *
     * @returns {boolean} True if refresh needed
     */
    function shouldRefresh() {
        if (!_token || !_tokenTime) return true;
        const age = Date.now() - _tokenTime;
        return age > (CONFIG.tokenLifetime - CONFIG.refreshThreshold);
    }

    /**
     * Refresh the CSRF token from the server.
     *
     * @returns {Promise<string>} The new token
     */
    async function refresh() {
        // Avoid duplicate refresh requests
        if (_pendingRefresh) {
            return _pendingRefresh;
        }

        _pendingRefresh = (async () => {
            try {
                const response = await fetch(CONFIG.refreshEndpoint, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {
                        'Accept': 'application/json'
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.token) {
                        setToken(data.token);
                        console.log('[CSRF] Token refreshed');
                        return _token;
                    }
                }

                console.warn('[CSRF] Token refresh failed');
                return _token;
            } catch (error) {
                console.error('[CSRF] Token refresh error:', error);
                return _token;
            } finally {
                _pendingRefresh = null;
            }
        })();

        return _pendingRefresh;
    }

    /**
     * Schedule automatic token refresh.
     */
    function scheduleRefresh() {
        if (_refreshTimer) {
            clearTimeout(_refreshTimer);
        }

        if (_tokenTime) {
            const refreshTime = CONFIG.tokenLifetime - CONFIG.refreshThreshold;
            _refreshTimer = setTimeout(refresh, refreshTime);
        }
    }

    /**
     * Add CSRF token to a headers object.
     *
     * @param {Object|Headers} headers - Headers object to modify
     * @returns {Object|Headers} The modified headers
     */
    function addToHeaders(headers) {
        const token = getToken();
        if (!token) return headers;

        if (headers instanceof Headers) {
            headers.set(CONFIG.headerName, token);
        } else {
            headers[CONFIG.headerName] = token;
        }
        return headers;
    }

    /**
     * Add CSRF token hidden input to a form.
     *
     * @param {HTMLFormElement} form - The form element
     */
    function addToForm(form) {
        if (!form || !(form instanceof HTMLFormElement)) {
            console.warn('[CSRF] Invalid form element');
            return;
        }

        // Remove existing CSRF input if present
        const existing = form.querySelector(`input[name="${CONFIG.formFieldName}"]`);
        if (existing) {
            existing.remove();
        }

        // Add new hidden input
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = CONFIG.formFieldName;
        input.value = getToken() || '';
        form.appendChild(input);
    }

    /**
     * Add CSRF protection to all forms on the page.
     */
    function protectAllForms() {
        document.querySelectorAll('form').forEach(form => {
            // Skip forms that already have CSRF tokens
            if (!form.querySelector(`input[name="${CONFIG.formFieldName}"]`)) {
                addToForm(form);
            }

            // Also add on submit to ensure fresh token
            form.addEventListener('submit', function() {
                addToForm(this);
            });
        });
    }

    /**
     * Create a FormData with CSRF token included.
     *
     * @param {HTMLFormElement} [form] - Optional form to base FormData on
     * @returns {FormData} FormData with CSRF token
     */
    function createFormData(form) {
        const formData = form ? new FormData(form) : new FormData();
        const token = getToken();
        if (token) {
            formData.set(CONFIG.formFieldName, token);
        }
        return formData;
    }

    /**
     * Get a cookie value by name.
     *
     * @param {string} name - Cookie name
     * @returns {string|null} Cookie value
     */
    function getCookie(name) {
        const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : null;
    }

    /**
     * Patch the global fetch to automatically add CSRF tokens.
     */
    function patchFetch() {
        const originalFetch = window.fetch;

        window.fetch = function(url, options = {}) {
            // Only add CSRF for same-origin requests with modifying methods
            const method = (options.method || 'GET').toUpperCase();
            const modifyingMethods = ['POST', 'PUT', 'DELETE', 'PATCH'];

            if (modifyingMethods.includes(method)) {
                // Check if same-origin
                try {
                    const requestUrl = new URL(url, window.location.origin);
                    if (requestUrl.origin === window.location.origin) {
                        // Add CSRF header
                        options.headers = options.headers || {};
                        const token = getToken();
                        if (token) {
                            if (options.headers instanceof Headers) {
                                options.headers.set(CONFIG.headerName, token);
                            } else {
                                options.headers[CONFIG.headerName] = token;
                            }
                        }
                    }
                } catch (e) {
                    // Invalid URL, let original fetch handle it
                }
            }

            return originalFetch.call(this, url, options);
        };
    }

    /**
     * Handle CSRF error responses.
     * Returns true if the error was a CSRF error and was handled.
     *
     * @param {Response} response - Fetch response
     * @param {Object} data - Parsed response data
     * @returns {boolean} True if CSRF error was handled
     */
    async function handleError(response, data) {
        if (response.status === 403 && data.code === 'CSRF_INVALID') {
            console.warn('[CSRF] Token rejected, refreshing...');

            // Refresh token
            await refresh();

            // Optionally retry the request (caller should handle this)
            return true;
        }
        return false;
    }

    /**
     * Generate HTML for a hidden CSRF input.
     *
     * @returns {string} HTML string
     */
    function htmlField() {
        const token = getToken() || '';
        return `<input type="hidden" name="${CONFIG.formFieldName}" value="${escapeHtml(token)}">`;
    }

    /**
     * Escape HTML entities.
     *
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    function escapeHtml(str) {
        if (!str) return '';
        const htmlEscapes = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        };
        return String(str).replace(/[&<>"']/g, char => htmlEscapes[char]);
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
        getToken,
        setToken,
        refresh,
        addToHeaders,
        addToForm,
        protectAllForms,
        createFormData,
        handleError,
        htmlField,
        CONFIG
    };
})();

// Expose globally
window.CSRF = CSRF;
