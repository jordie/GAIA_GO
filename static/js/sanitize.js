/**
 * XSS Prevention Utilities for Architect Dashboard
 *
 * This module provides client-side sanitization functions to prevent
 * Cross-Site Scripting (XSS) attacks. ALL user-provided data must be
 * sanitized before being inserted into the DOM.
 *
 * Usage:
 *   import { escapeHtml, sanitizeForDom, safeSetText } from './sanitize.js';
 *
 *   // When inserting text content
 *   element.textContent = userInput; // SAFE - automatically escaped
 *
 *   // When building HTML strings (AVOID if possible)
 *   const html = `<span>${escapeHtml(userInput)}</span>`;
 *
 *   // When using innerHTML (use safeSetHtml instead)
 *   safeSetHtml(element, userInput); // Escapes and sets safely
 */

// ============================================================================
// CORE SANITIZATION FUNCTIONS
// ============================================================================

/**
 * Escape HTML special characters to prevent XSS.
 *
 * @param {string} str - String to escape
 * @returns {string} HTML-escaped string
 *
 * @example
 * escapeHtml('<script>alert("xss")</script>')
 * // Returns: '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
 */
function escapeHtml(str) {
    if (str === null || str === undefined) {
        return '';
    }

    if (typeof str !== 'string') {
        str = String(str);
    }

    const htmlEscapes = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '`': '&#x60;',
        '/': '&#x2F;'
    };

    return str.replace(/[&<>"'`\/]/g, char => htmlEscapes[char]);
}

/**
 * Escape string for use in JavaScript string literals.
 *
 * @param {string} str - String to escape
 * @returns {string} JavaScript-escaped string
 */
function escapeJs(str) {
    if (str === null || str === undefined) {
        return '';
    }

    if (typeof str !== 'string') {
        str = String(str);
    }

    return str
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/'/g, "\\'")
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r')
        .replace(/</g, '\\x3c')
        .replace(/>/g, '\\x3e')
        .replace(/\u2028/g, '\\u2028')
        .replace(/\u2029/g, '\\u2029');
}

/**
 * Escape string for use in HTML attributes.
 *
 * @param {string} str - String to escape
 * @returns {string} Attribute-safe string
 */
function escapeAttribute(str) {
    if (str === null || str === undefined) {
        return '';
    }

    if (typeof str !== 'string') {
        str = String(str);
    }

    return str
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/`/g, '&#x60;');
}

/**
 * Sanitize a URL to prevent javascript: and data: XSS.
 *
 * @param {string} url - URL to sanitize
 * @param {string[]} allowedSchemes - Allowed URL schemes
 * @returns {string} Sanitized URL or empty string if dangerous
 */
function sanitizeUrl(url, allowedSchemes = ['http', 'https', 'mailto', 'tel']) {
    if (!url || typeof url !== 'string') {
        return '';
    }

    url = url.trim();

    // Remove any whitespace/control characters that could be used to bypass checks
    const normalized = url.toLowerCase().replace(/[\s\x00-\x1f]/g, '');

    // Check for dangerous schemes
    const dangerousPatterns = [
        'javascript:',
        'data:',
        'vbscript:',
        'file:',
        'blob:'
    ];

    for (const pattern of dangerousPatterns) {
        if (normalized.startsWith(pattern) || normalized.includes(pattern)) {
            console.warn('Blocked dangerous URL:', url);
            return '';
        }
    }

    // Validate scheme if present
    const schemeMatch = url.match(/^([a-z][a-z0-9+.-]*):\/\//i);
    if (schemeMatch) {
        const scheme = schemeMatch[1].toLowerCase();
        if (!allowedSchemes.includes(scheme)) {
            console.warn('Blocked URL with disallowed scheme:', url);
            return '';
        }
    }

    return url;
}

// ============================================================================
// DOM MANIPULATION HELPERS
// ============================================================================

/**
 * Safely set text content of an element.
 * Use this instead of textContent when you want explicit safety.
 *
 * @param {HTMLElement} element - Target element
 * @param {string} text - Text content to set
 */
function safeSetText(element, text) {
    if (!element) return;
    element.textContent = text ?? '';
}

/**
 * Safely set HTML content with escaping.
 * This escapes the content before setting innerHTML.
 *
 * @param {HTMLElement} element - Target element
 * @param {string} html - HTML string (will be escaped)
 */
function safeSetHtml(element, html) {
    if (!element) return;
    element.innerHTML = escapeHtml(html);
}

/**
 * Safely set an element's attribute value.
 *
 * @param {HTMLElement} element - Target element
 * @param {string} attr - Attribute name
 * @param {string} value - Attribute value
 */
function safeSetAttribute(element, attr, value) {
    if (!element) return;

    // Block dangerous attributes entirely
    const dangerousAttrs = ['onclick', 'onerror', 'onload', 'onmouseover',
                           'onfocus', 'onblur', 'onsubmit', 'onchange'];
    if (dangerousAttrs.includes(attr.toLowerCase())) {
        console.warn('Blocked dangerous attribute:', attr);
        return;
    }

    // Special handling for href and src
    if (attr === 'href' || attr === 'src') {
        value = sanitizeUrl(value);
        if (!value) return;
    }

    element.setAttribute(attr, escapeAttribute(value));
}

/**
 * Create a text node (always safe from XSS).
 *
 * @param {string} text - Text content
 * @returns {Text} Text node
 */
function createSafeTextNode(text) {
    return document.createTextNode(text ?? '');
}

/**
 * Create an element with safe attributes and text content.
 *
 * @param {string} tag - Tag name
 * @param {Object} attrs - Attributes object
 * @param {string} text - Text content
 * @returns {HTMLElement} Created element
 */
function createSafeElement(tag, attrs = {}, text = null) {
    const element = document.createElement(tag);

    for (const [key, value] of Object.entries(attrs)) {
        safeSetAttribute(element, key, value);
    }

    if (text !== null) {
        element.textContent = text;
    }

    return element;
}

// ============================================================================
// TEMPLATE LITERAL HELPERS
// ============================================================================

/**
 * Tagged template literal for safe HTML with auto-escaping.
 *
 * @example
 * const userInput = '<script>alert(1)</script>';
 * const html = safeHtml`<div class="user-content">${userInput}</div>`;
 * // Result: '<div class="user-content">&lt;script&gt;alert(1)&lt;/script&gt;</div>'
 */
function safeHtml(strings, ...values) {
    let result = strings[0];
    for (let i = 0; i < values.length; i++) {
        result += escapeHtml(values[i]) + strings[i + 1];
    }
    return result;
}

/**
 * Tagged template literal that marks a string as trusted (already escaped).
 * USE WITH CAUTION - only for content that has already been sanitized.
 *
 * @example
 * const alreadyEscaped = escapeHtml(userInput);
 * const html = safeHtml`<div>${trusted(alreadyEscaped)}</div>`;
 */
function trusted(str) {
    return { __trusted: true, value: str };
}

/**
 * Enhanced safeHtml that supports trusted() values.
 *
 * @example
 * const name = '<script>xss</script>';
 * const icon = trusted('<i class="icon-check"></i>'); // Known safe
 * const html = html`<span>${icon} ${name}</span>`;
 */
function html(strings, ...values) {
    let result = strings[0];
    for (let i = 0; i < values.length; i++) {
        const val = values[i];
        if (val && val.__trusted) {
            result += val.value;
        } else {
            result += escapeHtml(val);
        }
        result += strings[i + 1];
    }
    return result;
}

// ============================================================================
// FORM SANITIZATION
// ============================================================================

/**
 * Sanitize all text inputs in a form before submission.
 *
 * @param {HTMLFormElement} form - Form element
 * @param {Object} options - Options
 * @param {string[]} options.exclude - Field names to exclude
 * @param {number} options.maxLength - Maximum length for text fields
 */
function sanitizeForm(form, options = {}) {
    const { exclude = [], maxLength = 10000 } = options;

    const inputs = form.querySelectorAll('input[type="text"], input[type="search"], textarea');

    inputs.forEach(input => {
        if (exclude.includes(input.name)) return;

        let value = input.value;

        // Trim whitespace
        value = value.trim();

        // Truncate if too long
        if (value.length > maxLength) {
            value = value.substring(0, maxLength);
        }

        // Remove null bytes
        value = value.replace(/\x00/g, '');

        input.value = value;
    });
}

/**
 * Get sanitized form data as an object.
 *
 * @param {HTMLFormElement} form - Form element
 * @returns {Object} Sanitized form data
 */
function getSanitizedFormData(form) {
    const formData = new FormData(form);
    const data = {};

    for (const [key, value] of formData.entries()) {
        if (typeof value === 'string') {
            data[key] = value.trim().replace(/\x00/g, '');
        } else {
            data[key] = value;
        }
    }

    return data;
}

// ============================================================================
// CONTENT SECURITY POLICY HELPERS
// ============================================================================

/**
 * Generate a random nonce for CSP.
 *
 * @returns {string} Random nonce string
 */
function generateNonce() {
    const array = new Uint8Array(16);
    crypto.getRandomValues(array);
    return btoa(String.fromCharCode.apply(null, array));
}

// ============================================================================
// INPUT VALIDATION
// ============================================================================

/**
 * Validate and sanitize user input based on type.
 *
 * @param {string} value - Input value
 * @param {string} type - Expected type: 'text', 'email', 'url', 'integer', 'number'
 * @param {Object} options - Validation options
 * @returns {Object} { valid: boolean, value: any, error: string|null }
 */
function validateInput(value, type, options = {}) {
    const { required = false, maxLength = 1000, minLength = 0, min, max } = options;

    // Handle required
    if (required && (!value || !value.toString().trim())) {
        return { valid: false, value: null, error: 'This field is required' };
    }

    if (!value && !required) {
        return { valid: true, value: '', error: null };
    }

    value = String(value).trim();

    switch (type) {
        case 'text':
            if (value.length > maxLength) {
                return { valid: false, value: null, error: `Maximum length is ${maxLength} characters` };
            }
            if (value.length < minLength) {
                return { valid: false, value: null, error: `Minimum length is ${minLength} characters` };
            }
            return { valid: true, value: value, error: null };

        case 'email':
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                return { valid: false, value: null, error: 'Invalid email address' };
            }
            return { valid: true, value: value.toLowerCase(), error: null };

        case 'url':
            const sanitized = sanitizeUrl(value);
            if (!sanitized) {
                return { valid: false, value: null, error: 'Invalid or unsafe URL' };
            }
            return { valid: true, value: sanitized, error: null };

        case 'integer':
            const intVal = parseInt(value, 10);
            if (isNaN(intVal)) {
                return { valid: false, value: null, error: 'Must be a whole number' };
            }
            if (min !== undefined && intVal < min) {
                return { valid: false, value: null, error: `Minimum value is ${min}` };
            }
            if (max !== undefined && intVal > max) {
                return { valid: false, value: null, error: `Maximum value is ${max}` };
            }
            return { valid: true, value: intVal, error: null };

        case 'number':
            const numVal = parseFloat(value);
            if (isNaN(numVal)) {
                return { valid: false, value: null, error: 'Must be a number' };
            }
            if (min !== undefined && numVal < min) {
                return { valid: false, value: null, error: `Minimum value is ${min}` };
            }
            if (max !== undefined && numVal > max) {
                return { valid: false, value: null, error: `Maximum value is ${max}` };
            }
            return { valid: true, value: numVal, error: null };

        default:
            return { valid: true, value: value, error: null };
    }
}

// ============================================================================
// EXPORT FOR MODULE USAGE
// ============================================================================

// For ES6 modules
if (typeof window !== 'undefined') {
    window.Sanitize = {
        // Core functions
        escapeHtml,
        escapeJs,
        escapeAttribute,
        sanitizeUrl,

        // DOM helpers
        safeSetText,
        safeSetHtml,
        safeSetAttribute,
        createSafeTextNode,
        createSafeElement,

        // Template literals
        safeHtml,
        html,
        trusted,

        // Form handling
        sanitizeForm,
        getSanitizedFormData,

        // Validation
        validateInput,

        // CSP
        generateNonce
    };
}

// For CommonJS
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        escapeHtml,
        escapeJs,
        escapeAttribute,
        sanitizeUrl,
        safeSetText,
        safeSetHtml,
        safeSetAttribute,
        createSafeTextNode,
        createSafeElement,
        safeHtml,
        html,
        trusted,
        sanitizeForm,
        getSanitizedFormData,
        validateInput,
        generateNonce
    };
}
