/**
 * Table/Grid Search & Filter Functions
 * Provides search and filter functionality for all dashboard tables
 */

// Generic filter function for paginated tables
function filterTable(tableName, searchId, filterFields) {
    const searchInput = document.getElementById(searchId);
    const searchTerm = (searchInput?.value || '').toLowerCase().trim();
    const state = paginationState[tableName];

    if (!state) return;

    // Store original data on first filter
    if (!state.originalData || state.originalData.length === 0) {
        state.originalData = [...state.data];
    }

    let filtered = state.originalData;

    if (searchTerm) {
        filtered = filtered.filter(item => {
            return filterFields.some(field => {
                const value = item[field];
                return value && String(value).toLowerCase().includes(searchTerm);
            });
        });
    }

    state.data = filtered;
    state.total = filtered.length;
    state.page = 1;
    renderPaginatedTable(tableName);
}

// Reset filter and restore original data
function resetTableFilter(tableName) {
    const state = paginationState[tableName];
    if (!state || !state.originalData) return;

    state.data = [...state.originalData];
    state.total = state.data.length;
    state.page = 1;
    state.originalData = [];
    renderPaginatedTable(tableName);
}

// Filter errors table
function filterErrorsTable() {
    filterTable('errors', 'errorSearch', ['message', 'source', 'error_type', 'node_hostname']);
}

// Filter tasks table
function filterTasksTable() {
    filterTable('tasks', 'taskSearch', ['task_type', 'task_data', 'result', 'worker_id']);
}

// Filter workers table
function filterWorkersTable() {
    const searchInput = document.getElementById('workerSearch');
    const statusFilter = document.getElementById('workerStatusFilter');
    const searchTerm = (searchInput?.value || '').toLowerCase().trim();
    const statusValue = statusFilter?.value || '';
    const state = paginationState.workers;

    if (!state) return;

    // Store original data on first filter
    if (!state.originalData || state.originalData.length === 0) {
        state.originalData = [...state.data];
    }

    let filtered = state.originalData;

    if (searchTerm) {
        filtered = filtered.filter(w =>
            (w.id && w.id.toLowerCase().includes(searchTerm)) ||
            (w.worker_type && w.worker_type.toLowerCase().includes(searchTerm)) ||
            (w.node_id && w.node_id.toLowerCase().includes(searchTerm))
        );
    }

    if (statusValue) {
        filtered = filtered.filter(w => w.status === statusValue);
    }

    state.data = filtered;
    state.total = filtered.length;
    state.page = 1;
    renderPaginatedTable('workers');
}

// Filter deployments table
function filterDeploymentsTable() {
    filterTable('deployments', 'deploymentSearch', ['tag', 'environment', 'deployed_by', 'status']);
}

// Filter bugs grid (card-based)
function filterBugsTable() {
    const searchInput = document.getElementById('bugSearch');
    const searchTerm = (searchInput?.value || '').toLowerCase().trim();
    const grid = document.getElementById('bugsGrid');
    if (!grid) return;

    const cards = grid.querySelectorAll('.card');
    cards.forEach(card => {
        const title = card.querySelector('.card-title')?.textContent?.toLowerCase() || '';
        const meta = card.querySelector('.card-meta')?.textContent?.toLowerCase() || '';
        const body = card.querySelector('.card-body')?.textContent?.toLowerCase() || '';
        const badges = Array.from(card.querySelectorAll('.badge')).map(b => b.textContent.toLowerCase()).join(' ');

        const matches = !searchTerm ||
            title.includes(searchTerm) ||
            meta.includes(searchTerm) ||
            body.includes(searchTerm) ||
            badges.includes(searchTerm);

        card.style.display = matches ? '' : 'none';
    });

    // Update visible count
    const visibleCount = Array.from(cards).filter(c => c.style.display !== 'none').length;
    updateFilterCount('bugs', visibleCount, cards.length);
}

// Filter nodes grid (card-based)
function filterNodesGrid() {
    const searchInput = document.getElementById('nodeSearch');
    const statusFilter = document.getElementById('nodeStatusFilter');
    const searchTerm = (searchInput?.value || '').toLowerCase().trim();
    const statusValue = statusFilter?.value || '';
    const grid = document.getElementById('nodesGrid');
    if (!grid) return;

    const cards = grid.querySelectorAll('.card');
    cards.forEach(card => {
        const title = card.querySelector('.card-title')?.textContent?.toLowerCase() || '';
        const meta = card.querySelector('.card-meta')?.textContent?.toLowerCase() || '';
        const body = card.querySelector('.card-body')?.textContent?.toLowerCase() || '';
        const statusBadge = card.querySelector('.badge')?.textContent?.toLowerCase() || '';

        const matchesSearch = !searchTerm ||
            title.includes(searchTerm) ||
            meta.includes(searchTerm) ||
            body.includes(searchTerm);

        const matchesStatus = !statusValue || statusBadge.includes(statusValue);

        card.style.display = (matchesSearch && matchesStatus) ? '' : 'none';
    });

    // Update visible count
    const visibleCount = Array.from(cards).filter(c => c.style.display !== 'none').length;
    updateFilterCount('nodes', visibleCount, cards.length);
}

// Helper to update filter count display
function updateFilterCount(type, visible, total) {
    const countEl = document.getElementById(`${type}FilterCount`);
    if (countEl) {
        if (visible === total) {
            countEl.textContent = '';
        } else {
            countEl.textContent = `Showing ${visible} of ${total}`;
        }
    }
}

// Clear search input and reset filter
function clearSearch(inputId, filterFn) {
    const input = document.getElementById(inputId);
    if (input) {
        input.value = '';
        if (typeof filterFn === 'function') {
            filterFn();
        }
    }
}

// Debounce helper for search inputs
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Create debounced versions for better performance
const debouncedFilterErrors = debounce(filterErrorsTable, 300);
const debouncedFilterTasks = debounce(filterTasksTable, 300);
const debouncedFilterWorkers = debounce(filterWorkersTable, 300);
const debouncedFilterDeployments = debounce(filterDeploymentsTable, 300);
const debouncedFilterBugs = debounce(filterBugsTable, 300);
const debouncedFilterNodes = debounce(filterNodesGrid, 300);

console.log('[TableFilters] Search and filter functions loaded');
