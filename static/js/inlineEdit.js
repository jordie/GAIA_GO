/**
 * Inline Editing Module
 *
 * Provides inline editing functionality for task fields across the dashboard.
 *
 * Usage:
 *   InlineEdit.make(element, {
 *     type: 'text',           // text, textarea, select, number, date
 *     field: 'name',          // Field name for API
 *     entityType: 'feature',  // feature, bug, task
 *     entityId: 123,          // Entity ID
 *     options: [],            // For select type: [{value, label}]
 *     onSave: (value) => {},  // Optional callback after save
 *     validate: (value) => {} // Optional validation
 *   });
 */

const InlineEdit = (function() {
    'use strict';

    // Track active editor to prevent multiple editors
    let activeEditor = null;

    /**
     * Escape HTML to prevent XSS attacks.
     * Uses global Sanitize if available, otherwise falls back to local implementation.
     */
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        if (typeof str !== 'string') str = String(str);
        if (typeof window.Sanitize !== 'undefined' && window.Sanitize.escapeHtml) {
            return window.Sanitize.escapeHtml(str);
        }
        // Fallback implementation
        const htmlEscapes = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        };
        return str.replace(/[&<>"']/g, char => htmlEscapes[char]);
    }

    // API endpoints for each entity type
    const API_ENDPOINTS = {
        feature: '/api/features',
        bug: '/api/bugs',
        task: '/api/tasks',
        milestone: '/api/milestones',
        project: '/api/projects',
        devops_task: '/api/devops-tasks'
    };

    // Common field options
    const FIELD_OPTIONS = {
        status: {
            feature: [
                { value: 'planned', label: 'Planned' },
                { value: 'in_progress', label: 'In Progress' },
                { value: 'review', label: 'Review' },
                { value: 'testing', label: 'Testing' },
                { value: 'completed', label: 'Completed' },
                { value: 'blocked', label: 'Blocked' }
            ],
            bug: [
                { value: 'open', label: 'Open' },
                { value: 'in_progress', label: 'In Progress' },
                { value: 'resolved', label: 'Resolved' },
                { value: 'closed', label: 'Closed' },
                { value: 'wontfix', label: "Won't Fix" }
            ],
            task: [
                { value: 'pending', label: 'Pending' },
                { value: 'in_progress', label: 'In Progress' },
                { value: 'completed', label: 'Completed' },
                { value: 'failed', label: 'Failed' },
                { value: 'cancelled', label: 'Cancelled' }
            ]
        },
        priority: [
            { value: 'critical', label: 'Critical' },
            { value: 'high', label: 'High' },
            { value: 'medium', label: 'Medium' },
            { value: 'low', label: 'Low' }
        ],
        severity: [
            { value: 'critical', label: 'Critical' },
            { value: 'high', label: 'High' },
            { value: 'medium', label: 'Medium' },
            { value: 'low', label: 'Low' }
        ]
    };

    /**
     * Make an element inline-editable
     */
    function make(element, options) {
        if (!element || !options.entityType || !options.entityId || !options.field) {
            console.error('InlineEdit: Missing required options');
            return;
        }

        // Store options on element
        element.dataset.inlineEdit = JSON.stringify(options);
        element.classList.add('inline-editable');
        element.setAttribute('title', 'Click to edit');

        // Add click handler
        element.addEventListener('click', handleClick);

        // Add keyboard handler for accessibility
        element.setAttribute('tabindex', '0');
        element.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleClick.call(element, e);
            }
        });
    }

    /**
     * Handle click on editable element
     */
    function handleClick(e) {
        e.stopPropagation();

        // Close any existing editor
        if (activeEditor) {
            closeEditor(activeEditor, false);
        }

        const element = this;
        const options = JSON.parse(element.dataset.inlineEdit);

        // Create editor based on type
        const editor = createEditor(element, options);
        if (!editor) return;

        activeEditor = {
            element,
            editor,
            options,
            originalValue: element.textContent.trim()
        };

        // Replace content with editor
        element.classList.add('inline-editing');
        element.innerHTML = '';
        element.appendChild(editor);

        // Focus the editor
        if (editor.tagName === 'SELECT') {
            editor.focus();
        } else {
            editor.focus();
            // Select all text for text inputs
            if (editor.select) editor.select();
        }
    }

    /**
     * Create the appropriate editor element
     */
    function createEditor(element, options) {
        const type = options.type || 'text';
        const currentValue = element.textContent.trim();
        let editor;

        switch (type) {
            case 'textarea':
                editor = document.createElement('textarea');
                editor.value = currentValue;
                editor.rows = 3;
                editor.className = 'inline-editor inline-textarea';
                break;

            case 'select':
                editor = document.createElement('select');
                editor.className = 'inline-editor inline-select';

                // Get options based on field
                let selectOptions = options.options || [];
                if (!selectOptions.length && FIELD_OPTIONS[options.field]) {
                    if (options.field === 'status') {
                        selectOptions = FIELD_OPTIONS.status[options.entityType] || [];
                    } else {
                        selectOptions = FIELD_OPTIONS[options.field] || [];
                    }
                }

                selectOptions.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt.value;
                    option.textContent = opt.label;
                    // Match current value (case-insensitive)
                    if (opt.value.toLowerCase() === currentValue.toLowerCase() ||
                        opt.label.toLowerCase() === currentValue.toLowerCase()) {
                        option.selected = true;
                    }
                    editor.appendChild(option);
                });
                break;

            case 'number':
                editor = document.createElement('input');
                editor.type = 'number';
                editor.value = parseFloat(currentValue) || 0;
                editor.className = 'inline-editor inline-number';
                editor.min = options.min || 0;
                if (options.max) editor.max = options.max;
                if (options.step) editor.step = options.step;
                break;

            case 'date':
                editor = document.createElement('input');
                editor.type = 'date';
                editor.value = currentValue;
                editor.className = 'inline-editor inline-date';
                break;

            case 'text':
            default:
                editor = document.createElement('input');
                editor.type = 'text';
                editor.value = currentValue;
                editor.className = 'inline-editor inline-text';
                if (options.maxLength) editor.maxLength = options.maxLength;
                break;
        }

        // Add event handlers
        editor.addEventListener('blur', () => handleBlur());
        editor.addEventListener('keydown', handleKeydown);

        return editor;
    }

    /**
     * Handle keydown in editor
     */
    function handleKeydown(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeEditor(activeEditor, false);
        } else if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
            e.preventDefault();
            closeEditor(activeEditor, true);
        } else if (e.key === 'Enter' && e.ctrlKey && e.target.tagName === 'TEXTAREA') {
            e.preventDefault();
            closeEditor(activeEditor, true);
        }
    }

    /**
     * Handle blur (focus lost)
     */
    function handleBlur() {
        // Delay to allow click on save button if we add one
        setTimeout(() => {
            if (activeEditor) {
                closeEditor(activeEditor, true);
            }
        }, 150);
    }

    /**
     * Close the editor
     */
    async function closeEditor(editorState, save) {
        if (!editorState) return;

        const { element, editor, options, originalValue } = editorState;
        let newValue = editor.value;

        // For select, get the display label
        let displayValue = newValue;
        if (editor.tagName === 'SELECT' && editor.selectedIndex >= 0) {
            displayValue = editor.options[editor.selectedIndex].text;
        }

        // Validate if needed
        if (save && options.validate) {
            const validationError = options.validate(newValue);
            if (validationError) {
                showError(element, validationError);
                editor.focus();
                return;
            }
        }

        // Check if value changed
        const valueChanged = newValue !== originalValue &&
                            displayValue !== originalValue;

        // Reset element
        element.classList.remove('inline-editing');
        activeEditor = null;

        if (save && valueChanged) {
            // Show saving indicator (escape to prevent XSS)
            element.innerHTML = `<span class="inline-saving">${escapeHtml(displayValue)}</span>`;

            try {
                await saveValue(options, newValue);

                // Update display with new value
                element.textContent = displayValue;
                element.classList.add('inline-saved');
                setTimeout(() => element.classList.remove('inline-saved'), 1000);

                // Call onSave callback if provided
                if (options.onSave) {
                    options.onSave(newValue, displayValue);
                }

                // Show success notification
                if (typeof showNotification === 'function') {
                    showNotification(`${options.field} updated`, 'success');
                }

            } catch (error) {
                console.error('InlineEdit save failed:', error);
                element.textContent = originalValue;
                element.classList.add('inline-error');
                setTimeout(() => element.classList.remove('inline-error'), 2000);

                if (typeof showNotification === 'function') {
                    showNotification(`Failed to update ${options.field}: ${error.message}`, 'error');
                }
            }
        } else {
            // Restore original value
            element.textContent = originalValue;
        }
    }

    /**
     * Save value to API
     */
    async function saveValue(options, value) {
        const endpoint = API_ENDPOINTS[options.entityType];
        if (!endpoint) {
            throw new Error(`Unknown entity type: ${options.entityType}`);
        }

        const url = `${endpoint}/${options.entityId}`;
        const body = { [options.field]: value };

        // Use the global api function if available, otherwise fetch directly
        if (typeof api === 'function') {
            const result = await api(url, 'PUT', body);
            if (result.error) {
                throw new Error(result.error);
            }
            return result;
        } else {
            const response = await fetch(url, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Update failed');
            }

            return response.json();
        }
    }

    /**
     * Show validation error
     */
    function showError(element, message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'inline-validation-error';
        errorDiv.textContent = message;
        element.appendChild(errorDiv);
        setTimeout(() => errorDiv.remove(), 3000);
    }

    /**
     * Batch make multiple elements editable
     */
    function makeAll(selector, options) {
        document.querySelectorAll(selector).forEach(el => {
            const elOptions = { ...options };

            // Get entity info from data attributes if not provided
            if (!elOptions.entityId && el.dataset.entityId) {
                elOptions.entityId = parseInt(el.dataset.entityId);
            }
            if (!elOptions.entityType && el.dataset.entityType) {
                elOptions.entityType = el.dataset.entityType;
            }
            if (!elOptions.field && el.dataset.field) {
                elOptions.field = el.dataset.field;
            }
            if (!elOptions.type && el.dataset.editType) {
                elOptions.type = el.dataset.editType;
            }

            make(el, elOptions);
        });
    }

    /**
     * Create an editable element
     */
    function createEditable(content, options) {
        const span = document.createElement('span');
        span.textContent = content || '-';
        span.className = 'inline-editable';
        span.dataset.entityId = options.entityId;
        span.dataset.entityType = options.entityType;
        span.dataset.field = options.field;
        if (options.type) span.dataset.editType = options.type;

        make(span, options);
        return span;
    }

    /**
     * Generate HTML for an editable field
     * All content and attributes are escaped to prevent XSS
     */
    function html(content, options) {
        const type = escapeHtml(options.type || 'text');
        const entityId = escapeHtml(String(options.entityId || ''));
        const entityType = escapeHtml(options.entityType || '');
        const field = escapeHtml(options.field || '');
        const safeContent = escapeHtml(content) || '-';

        const attrs = [
            'class="inline-editable"',
            `data-entity-id="${entityId}"`,
            `data-entity-type="${entityType}"`,
            `data-field="${field}"`,
            `data-edit-type="${type}"`,
            'title="Click to edit"',
            'tabindex="0"'
        ].join(' ');

        return `<span ${attrs}>${safeContent}</span>`;
    }

    /**
     * Initialize inline editing for dynamically added elements
     */
    function init() {
        // Use event delegation for inline-editable elements
        document.addEventListener('click', (e) => {
            const target = e.target.closest('.inline-editable:not(.inline-editing)');
            if (target && target.dataset.inlineEdit) {
                handleClick.call(target, e);
            }
        });

        // Close editor on click outside
        document.addEventListener('click', (e) => {
            if (activeEditor && !activeEditor.element.contains(e.target)) {
                closeEditor(activeEditor, true);
            }
        });
    }

    // Public API
    return {
        make,
        makeAll,
        createEditable,
        html,
        init,
        FIELD_OPTIONS
    };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', InlineEdit.init);
} else {
    InlineEdit.init();
}
