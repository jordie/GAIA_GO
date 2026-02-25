/**
 * Keyboard Shortcuts Module
 *
 * Comprehensive keyboard navigation for the Architect Dashboard.
 * Implements vim-style navigation, command sequences, and quick actions.
 *
 * @module keyboardShortcuts
 */

(function(global) {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const CONFIG = {
        // Timeout for multi-key sequences (ms)
        sequenceTimeout: 1000,

        // Enable vim-style navigation
        vimNavigation: true,

        // Show visual feedback for shortcuts
        showFeedback: true,

        // Feedback display duration (ms)
        feedbackDuration: 1500,

        // Panel mapping for number keys 1-9
        panelNumbers: [
            'queue', 'overview', 'projects', 'features', 'bugs',
            'errors', 'tmux', 'nodes', 'workers'
        ],

        // "Go to" (g+key) navigation mapping
        goToMap: {
            'q': 'queue',
            'o': 'overview',
            'd': 'overview',  // 'd' for dashboard (alias)
            'p': 'projects',
            'm': 'milestones',
            'f': 'features',
            'b': 'bugs',
            'e': 'errors',
            's': 'tmux',      // 's' for sessions
            't': 'tmux',      // 't' for tmux (alias)
            'n': 'nodes',
            'w': 'workers',
            'c': 'focus',     // 'c' for concentrate/focus
            'k': 'tasks',     // 'k' for tasks (kanban)
            'v': 'vault',     // 'v' for vault/secrets
            'a': 'accounts',  // 'a' for accounts
            'y': 'system-overview', // 'y' for system
            'r': 'sop',       // 'r' for rules/sop
        }
    };

    // =========================================================================
    // State
    // =========================================================================

    let state = {
        pendingSequence: null,
        sequenceTimer: null,
        selectedIndex: -1,
        currentList: null,
        isEnabled: true,
        lastAction: null
    };

    // =========================================================================
    // Utility Functions
    // =========================================================================

    /**
     * Check if user is currently typing in an input field
     */
    function isTypingInInput() {
        const activeEl = document.activeElement;
        if (!activeEl) return false;

        const tagName = activeEl.tagName.toUpperCase();
        const isInput = tagName === 'INPUT' || tagName === 'TEXTAREA';
        const isEditable = activeEl.isContentEditable;
        const isSelect = tagName === 'SELECT';

        return isInput || isEditable || isSelect;
    }

    /**
     * Check if a modal is currently open
     */
    function isModalOpen() {
        return !!document.querySelector('.modal-overlay.active');
    }

    /**
     * Get current panel name
     */
    function getCurrentPanel() {
        return typeof currentPanel !== 'undefined' ? currentPanel : 'overview';
    }

    /**
     * Show visual feedback for shortcut activation
     */
    function showShortcutFeedback(message, type = 'info') {
        if (!CONFIG.showFeedback) return;

        // Use existing notification system if available
        if (typeof showNotification === 'function') {
            showNotification(message, type, CONFIG.feedbackDuration);
            return;
        }

        // Fallback: create temporary toast
        const toast = document.createElement('div');
        toast.className = 'shortcut-feedback';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--bg-tertiary, #21262d);
            color: var(--text-primary, #f0f6fc);
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            font-family: var(--terminal-font-family, monospace);
            z-index: 10000;
            opacity: 0;
            transition: opacity 0.2s;
            border: 1px solid var(--border, #30363d);
        `;
        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 200);
            }, CONFIG.feedbackDuration);
        });
    }

    /**
     * Clear pending sequence
     */
    function clearSequence() {
        state.pendingSequence = null;
        if (state.sequenceTimer) {
            clearTimeout(state.sequenceTimer);
            state.sequenceTimer = null;
        }
    }

    /**
     * Start a sequence with timeout
     */
    function startSequence(key) {
        state.pendingSequence = key;
        state.sequenceTimer = setTimeout(clearSequence, CONFIG.sequenceTimeout);
    }

    // =========================================================================
    // Navigation Functions
    // =========================================================================

    /**
     * Navigate to a panel
     */
    function goToPanel(panelName) {
        if (typeof navigateToPanel === 'function') {
            navigateToPanel(panelName);
            showShortcutFeedback(`→ ${panelName}`, 'info');
            return true;
        }
        return false;
    }

    /**
     * Refresh current panel
     */
    function refreshCurrentPanel() {
        if (typeof loadPanelData === 'function') {
            loadPanelData(getCurrentPanel());
            showShortcutFeedback('Refreshed', 'success');
            return true;
        }
        return false;
    }

    /**
     * Toggle sidebar visibility
     */
    function toggleSidebarShortcut() {
        if (typeof toggleSidebar === 'function') {
            toggleSidebar();
            return true;
        }
        return false;
    }

    /**
     * Toggle dark/light theme
     */
    function toggleTheme() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';

        // Add transition class
        html.classList.add('theme-transition');

        // Toggle theme
        if (newTheme === 'light') {
            html.setAttribute('data-theme', 'light');
        } else {
            html.removeAttribute('data-theme');
        }

        // Save preference
        localStorage.setItem('theme', newTheme);

        // Remove transition class after animation
        setTimeout(() => html.classList.remove('theme-transition'), 300);

        showShortcutFeedback(`Theme: ${newTheme}`, 'info');
        return true;
    }

    /**
     * Toggle focus mode
     */
    function toggleFocusModeShortcut() {
        if (typeof toggleFocusMode === 'function') {
            toggleFocusMode();
            return true;
        }
        return false;
    }

    /**
     * Show keyboard shortcuts help modal
     */
    function showShortcutsHelp() {
        if (typeof showModal === 'function') {
            showModal('keyboardShortcuts');
            return true;
        }
        return false;
    }

    /**
     * Focus global search
     */
    function focusSearch() {
        const searchInput = document.getElementById('globalSearch') ||
                           document.getElementById('globalSearchInput');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
            return true;
        }
        return false;
    }

    /**
     * Open new item modal (context-aware)
     */
    function openNewItemModal() {
        const panel = getCurrentPanel();
        const modalMap = {
            'projects': 'newProject',
            'features': 'newFeature',
            'bugs': 'newBug',
            'queue': 'newProject',
            'tasks': 'newTask',
            'nodes': 'newNode'
        };

        const modalName = modalMap[panel];
        if (modalName && typeof showModal === 'function') {
            showModal(modalName);
            showShortcutFeedback(`New ${panel.slice(0, -1)}`, 'info');
            return true;
        }

        showShortcutFeedback('No new item for this panel', 'warning');
        return false;
    }

    /**
     * Close current modal
     */
    function closeModal() {
        const activeModal = document.querySelector('.modal-overlay.active');
        if (activeModal) {
            const modalId = activeModal.id.replace('modal-', '');
            if (typeof hideModal === 'function') {
                hideModal(modalId);
                return true;
            }
        }
        return false;
    }

    /**
     * Save current form (Cmd/Ctrl+S)
     */
    function saveCurrentForm() {
        // Find visible modal with a form
        const activeModal = document.querySelector('.modal-overlay.active .modal');
        if (activeModal) {
            const submitBtn = activeModal.querySelector('button[type="submit"], .btn-primary');
            if (submitBtn) {
                submitBtn.click();
                showShortcutFeedback('Saved', 'success');
                return true;
            }
        }

        // Try inline edit save
        const saveBtn = document.querySelector('.inline-edit-actions .btn-primary');
        if (saveBtn) {
            saveBtn.click();
            showShortcutFeedback('Saved', 'success');
            return true;
        }

        return false;
    }

    // =========================================================================
    // List Navigation (Vim-style)
    // =========================================================================

    /**
     * Get the current list element for the active panel
     */
    function getCurrentList() {
        const panel = getCurrentPanel();
        const listSelectors = {
            'projects': '#projectsTable tbody, .project-grid',
            'features': '#featuresTable tbody, .features-list',
            'bugs': '#bugsTable tbody, .bugs-list',
            'errors': '#errorsTable tbody, .errors-list',
            'queue': '#queueTable tbody, .queue-list',
            'tmux': '.session-list, #sessionsList',
            'nodes': '.nodes-grid, #nodesGrid',
            'tasks': '#tasksTable tbody',
            'workers': '#workersTable tbody'
        };

        const selector = listSelectors[panel];
        if (!selector) return null;

        return document.querySelector(selector);
    }

    /**
     * Get selectable items in the current list
     */
    function getListItems() {
        const list = getCurrentList();
        if (!list) return [];

        // Try different item selectors
        const selectors = ['tr:not(.empty-row)', '.list-item', '.grid-item', '.card', '.session-item'];

        for (const selector of selectors) {
            const items = list.querySelectorAll(selector);
            if (items.length > 0) {
                return Array.from(items).filter(item => {
                    // Filter out hidden items
                    const style = window.getComputedStyle(item);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                });
            }
        }

        return [];
    }

    /**
     * Update visual selection in list
     */
    function updateListSelection(items, index) {
        // Remove previous selection
        items.forEach(item => item.classList.remove('keyboard-selected'));

        if (index >= 0 && index < items.length) {
            const selectedItem = items[index];
            selectedItem.classList.add('keyboard-selected');

            // Scroll into view if needed
            selectedItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }

        state.selectedIndex = index;
    }

    /**
     * Move selection down in list
     */
    function moveDown() {
        const items = getListItems();
        if (items.length === 0) return false;

        let newIndex = state.selectedIndex + 1;
        if (newIndex >= items.length) newIndex = items.length - 1;

        updateListSelection(items, newIndex);
        return true;
    }

    /**
     * Move selection up in list
     */
    function moveUp() {
        const items = getListItems();
        if (items.length === 0) return false;

        let newIndex = state.selectedIndex - 1;
        if (newIndex < 0) newIndex = 0;

        updateListSelection(items, newIndex);
        return true;
    }

    /**
     * Go to first item in list
     */
    function goToFirst() {
        const items = getListItems();
        if (items.length === 0) return false;

        updateListSelection(items, 0);
        return true;
    }

    /**
     * Go to last item in list
     */
    function goToLast() {
        const items = getListItems();
        if (items.length === 0) return false;

        updateListSelection(items, items.length - 1);
        return true;
    }

    /**
     * Open/activate selected item
     */
    function openSelectedItem() {
        const items = getListItems();
        if (state.selectedIndex < 0 || state.selectedIndex >= items.length) {
            return false;
        }

        const selectedItem = items[state.selectedIndex];

        // Try clicking the item or its first link/button
        const clickable = selectedItem.querySelector('a, button, [onclick]') || selectedItem;
        if (clickable) {
            clickable.click();
            return true;
        }

        return false;
    }

    /**
     * Delete selected item (with confirmation)
     */
    function deleteSelectedItem() {
        const items = getListItems();
        if (state.selectedIndex < 0 || state.selectedIndex >= items.length) {
            return false;
        }

        const selectedItem = items[state.selectedIndex];
        const deleteBtn = selectedItem.querySelector('.delete-btn, [data-action="delete"], .btn-danger');

        if (deleteBtn) {
            deleteBtn.click();
            return true;
        }

        return false;
    }

    /**
     * Edit selected item
     */
    function editSelectedItem() {
        const items = getListItems();
        if (state.selectedIndex < 0 || state.selectedIndex >= items.length) {
            return false;
        }

        const selectedItem = items[state.selectedIndex];
        const editBtn = selectedItem.querySelector('.edit-btn, [data-action="edit"], .btn-edit');

        if (editBtn) {
            editBtn.click();
            return true;
        }

        // Try double-click for inline edit
        const event = new MouseEvent('dblclick', { bubbles: true });
        selectedItem.dispatchEvent(event);
        return true;
    }

    // =========================================================================
    // Main Keyboard Handler
    // =========================================================================

    function handleKeyDown(e) {
        // Skip if disabled
        if (!state.isEnabled) return;

        const key = e.key;
        const isCtrl = e.ctrlKey || e.metaKey;
        const isShift = e.shiftKey;
        const isAlt = e.altKey;

        // =====================================================================
        // Always-active shortcuts (work even when typing)
        // =====================================================================

        // Escape - close modal, clear selection, exit focus mode
        if (key === 'Escape') {
            if (closeModal()) {
                e.preventDefault();
                return;
            }
            if (document.body.classList.contains('focus-mode')) {
                toggleFocusModeShortcut();
                e.preventDefault();
                return;
            }
            // Clear list selection
            const items = getListItems();
            if (items.length > 0) {
                items.forEach(item => item.classList.remove('keyboard-selected'));
                state.selectedIndex = -1;
            }
            clearSequence();
            return;
        }

        // Cmd/Ctrl+K - Global search
        if (isCtrl && key === 'k') {
            e.preventDefault();
            focusSearch();
            return;
        }

        // Cmd/Ctrl+S - Save
        if (isCtrl && key === 's') {
            e.preventDefault();
            saveCurrentForm();
            return;
        }

        // Cmd/Ctrl+Shift+F - Toggle focus mode
        if (isCtrl && isShift && key === 'F') {
            e.preventDefault();
            toggleFocusModeShortcut();
            return;
        }

        // Cmd/Ctrl+Shift+L - Toggle theme
        if (isCtrl && isShift && key === 'L') {
            e.preventDefault();
            toggleTheme();
            return;
        }

        // =====================================================================
        // Skip if typing in input
        // =====================================================================

        if (isTypingInInput()) {
            // Allow Cmd/Ctrl combinations while typing
            if (!isCtrl) return;
        }

        // Skip if modal is open (except for specific shortcuts)
        if (isModalOpen() && !['Escape', 'Enter'].includes(key)) {
            return;
        }

        // =====================================================================
        // Sequence handling (G + key)
        // =====================================================================

        if (state.pendingSequence === 'g') {
            e.preventDefault();
            clearSequence();

            const lowerKey = key.toLowerCase();

            // Shift+G goes to last item (vim-style)
            if (isShift && lowerKey === 'g') {
                goToLast();
                return;
            }

            const panel = CONFIG.goToMap[lowerKey];
            if (panel) {
                goToPanel(panel);
            }
            return;
        }

        // =====================================================================
        // Single-key shortcuts
        // =====================================================================

        // ? or Shift+/ - Show help
        if (key === '?' || (isShift && key === '/')) {
            e.preventDefault();
            showShortcutsHelp();
            return;
        }

        // / - Focus search (when not in sequence)
        if (key === '/' && !state.pendingSequence) {
            e.preventDefault();
            focusSearch();
            return;
        }

        // [ or ] - Toggle sidebar
        if (key === '[' || key === ']') {
            e.preventDefault();
            toggleSidebarShortcut();
            return;
        }

        // R - Refresh
        if (key === 'r' || key === 'R') {
            e.preventDefault();
            refreshCurrentPanel();
            return;
        }

        // N - New item
        if ((key === 'n' || key === 'N') && !isCtrl) {
            e.preventDefault();
            openNewItemModal();
            return;
        }

        // G - Start "Go to" sequence
        if (key === 'g' || key === 'G') {
            startSequence('g');
            return;
        }

        // Number keys 1-9 - Quick panel navigation
        if (!isCtrl && !isAlt && key >= '1' && key <= '9') {
            const index = parseInt(key) - 1;
            if (CONFIG.panelNumbers[index]) {
                e.preventDefault();
                goToPanel(CONFIG.panelNumbers[index]);
            }
            return;
        }

        // =====================================================================
        // Vim-style list navigation
        // =====================================================================

        if (CONFIG.vimNavigation) {
            // J or Down - Move down
            if (key === 'j' || key === 'J' || key === 'ArrowDown') {
                e.preventDefault();
                moveDown();
                return;
            }

            // K or Up - Move up
            if (key === 'k' || key === 'K' || key === 'ArrowUp') {
                e.preventDefault();
                moveUp();
                return;
            }

            // Enter or O - Open selected
            if (key === 'Enter' || key === 'o' || key === 'O') {
                if (state.selectedIndex >= 0) {
                    e.preventDefault();
                    openSelectedItem();
                }
                return;
            }

            // Home or gg - Go to first
            if (key === 'Home') {
                e.preventDefault();
                goToFirst();
                return;
            }

            // End - Go to last
            if (key === 'End') {
                e.preventDefault();
                goToLast();
                return;
            }

            // E - Edit selected
            if (key === 'e' && state.selectedIndex >= 0) {
                e.preventDefault();
                editSelectedItem();
                return;
            }

            // X or Delete - Delete selected (with confirmation)
            if ((key === 'x' || key === 'Delete') && state.selectedIndex >= 0) {
                e.preventDefault();
                deleteSelectedItem();
                return;
            }
        }
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    /**
     * Add required CSS for keyboard navigation
     */
    function injectStyles() {
        const styleId = 'keyboard-shortcuts-styles';
        if (document.getElementById(styleId)) return;

        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            /* Keyboard selection highlight */
            .keyboard-selected {
                outline: 2px solid var(--accent, #58a6ff) !important;
                outline-offset: -2px;
                background: var(--bg-hover, rgba(88, 166, 255, 0.1)) !important;
            }

            /* Keyboard selected row in tables */
            tr.keyboard-selected td {
                background: var(--bg-hover, rgba(88, 166, 255, 0.1)) !important;
            }

            /* Shortcut feedback toast */
            .shortcut-feedback {
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            }

            /* Kbd styling in help modal */
            .shortcut-row {
                display: flex;
                justify-content: space-between;
                padding: 6px 16px;
                font-size: 13px;
                border-bottom: 1px solid var(--border, #30363d);
            }

            .shortcut-row:last-child {
                border-bottom: none;
            }

            .shortcut-keys {
                color: var(--text-secondary, #8b949e);
                font-family: var(--terminal-font-family, monospace);
            }

            .shortcut-keys kbd {
                background: var(--bg-tertiary, #21262d);
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                border: 1px solid var(--border, #30363d);
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Initialize keyboard shortcuts
     */
    function init() {
        // Inject styles
        injectStyles();

        // Remove any existing listener to prevent duplicates
        document.removeEventListener('keydown', handleKeyDown);

        // Add keyboard listener
        document.addEventListener('keydown', handleKeyDown);

        // Reset selection when panel changes
        if (typeof window.addEventListener === 'function') {
            window.addEventListener('hashchange', () => {
                state.selectedIndex = -1;
                const items = getListItems();
                items.forEach(item => item.classList.remove('keyboard-selected'));
            });
        }

        console.log('[KeyboardShortcuts] Initialized - Press ? for help');
    }

    // =========================================================================
    // Public API
    // =========================================================================

    const KeyboardShortcuts = {
        init,

        // Enable/disable shortcuts
        enable: () => { state.isEnabled = true; },
        disable: () => { state.isEnabled = false; },
        isEnabled: () => state.isEnabled,

        // Configuration
        setConfig: (key, value) => { CONFIG[key] = value; },
        getConfig: () => ({ ...CONFIG }),

        // Navigation
        goToPanel,
        refreshCurrentPanel,
        toggleSidebar: toggleSidebarShortcut,
        toggleTheme,
        toggleFocusMode: toggleFocusModeShortcut,
        focusSearch,

        // List navigation
        moveUp,
        moveDown,
        goToFirst,
        goToLast,
        openSelected: openSelectedItem,

        // State
        getSelectedIndex: () => state.selectedIndex,
        clearSelection: () => {
            const items = getListItems();
            items.forEach(item => item.classList.remove('keyboard-selected'));
            state.selectedIndex = -1;
        }
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Export to global scope
    global.KeyboardShortcuts = KeyboardShortcuts;

})(typeof window !== 'undefined' ? window : this);
