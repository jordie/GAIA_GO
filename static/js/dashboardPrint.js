(function() {
    'use strict';

    const limits = {
        projects: 8,
        features: 8,
        bugs: 8,
        errors: 8,
        pendingTasks: 10,
        runningTasks: 6,
        nodes: 8
    };

    const state = {
        generatedAt: new Date(),
        stats: null,
        projects: [],
        features: [],
        bugs: [],
        errors: [],
        errorsTotal: null,
        pendingTasks: [],
        runningTasks: [],
        nodes: [],
        workers: null,
        activity: []
    };

    const statusClassMap = {
        open: 'danger',
        pending: 'warning',
        running: 'info',
        in_progress: 'warning',
        completed: 'success',
        resolved: 'success',
        failed: 'danger',
        idle: 'muted',
        active: 'info',
        offline: 'danger',
        online: 'success',
        ignored: 'muted'
    };

    function getEl(id) {
        return document.getElementById(id);
    }

    function setText(id, text) {
        const el = getEl(id);
        if (el) {
            el.textContent = text;
        }
    }

    function safeNumber(value) {
        return typeof value === 'number' && !Number.isNaN(value) ? value : 0;
    }

    function formatDateTime(value) {
        if (!value) return '-';
        const date = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(date.getTime())) return '-';
        return date.toLocaleString(undefined, {
            year: 'numeric',
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function formatDate(value) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '-';
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: '2-digit'
        });
    }

    function formatAge(minutes) {
        if (minutes === null || minutes === undefined || Number.isNaN(minutes)) return '-';
        const value = Number(minutes);
        if (value < 60) return `${value.toFixed(0)}m`;
        if (value < 1440) return `${(value / 60).toFixed(1)}h`;
        return `${(value / 1440).toFixed(1)}d`;
    }

    function formatPercent(value) {
        if (value === null || value === undefined || Number.isNaN(value)) return '-';
        return `${Number(value).toFixed(1)}%`;
    }

    function formatStatusLabel(value) {
        if (!value) return 'Unknown';
        return String(value)
            .replace(/_/g, ' ')
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function statusClass(value) {
        const key = String(value || '').toLowerCase();
        return statusClassMap[key] || 'muted';
    }

    function createPill(label, value) {
        const pill = document.createElement('span');
        pill.className = `pill ${statusClass(value)}`;
        pill.textContent = label;
        return pill;
    }

    async function fetchJson(url) {
        const response = await fetch(url, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin'
        });
        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }
        return response.json();
    }

    function normalizeList(payload) {
        if (!payload) return [];
        if (Array.isArray(payload)) return payload;
        if (Array.isArray(payload.items)) return payload.items;
        if (Array.isArray(payload.errors)) return payload.errors;
        return [];
    }

    function renderTable(tableId, emptyId, rows, columns) {
        const table = getEl(tableId);
        if (!table) return;
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (!rows || rows.length === 0) {
            const empty = getEl(emptyId);
            if (empty) empty.style.display = 'block';
            return;
        }

        const empty = getEl(emptyId);
        if (empty) empty.style.display = 'none';

        rows.forEach((row) => {
            const tr = document.createElement('tr');
            columns.forEach((column) => {
                const td = document.createElement('td');
                if (column.mono) td.classList.add('mono');

                let value = column.render ? column.render(row) : row[column.key];
                if (value instanceof Node) {
                    td.appendChild(value);
                } else {
                    if (value === null || value === undefined || value === '') {
                        value = '-';
                    }
                    td.textContent = value;
                }

                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function updateSummary() {
        const stats = state.stats || {};
        const projectsTotal = safeNumber(stats.projects);
        const featuresTotal = safeNumber(stats.features && stats.features.total);
        const featuresInProgress = safeNumber(stats.features && stats.features.in_progress);
        const bugsTotal = safeNumber(stats.bugs && stats.bugs.total);
        const bugsOpen = safeNumber(stats.bugs && stats.bugs.open);

        const errorsStats = stats.errors || {};
        const errorOpenCount = errorsStats.open ? safeNumber(errorsStats.open.count) : 0;
        const errorOpenOccurrences = errorsStats.open ? safeNumber(errorsStats.open.occurrences) : 0;

        const tasksPending = safeNumber(stats.tasks && stats.tasks.pending);
        const tasksRunning = safeNumber(stats.tasks && stats.tasks.running);

        const nodesOnline = safeNumber(stats.nodes && stats.nodes.online);
        const workersActive = safeNumber(state.workers && state.workers.stats && state.workers.stats.active);
        const nodesTotal = stats.nodes
            ? Object.values(stats.nodes).reduce((sum, value) => sum + safeNumber(value), 0)
            : 0;

        const featuresFilteredTotal = stats.features && Object.prototype.hasOwnProperty.call(stats.features, 'in_progress')
            ? featuresInProgress
            : featuresTotal;
        const bugsFilteredTotal = stats.bugs && Object.prototype.hasOwnProperty.call(stats.bugs, 'open')
            ? bugsOpen
            : bugsTotal;

        setText('summaryProjects', projectsTotal);
        setText('summaryProjectsMeta', `${projectsTotal} active projects`);

        setText('summaryFeatures', featuresTotal);
        setText('summaryFeaturesMeta', `${featuresInProgress} in progress`);

        setText('summaryBugs', bugsTotal);
        setText('summaryBugsMeta', `${bugsOpen} open`);

        setText('summaryErrors', errorOpenCount);
        setText('summaryErrorsMeta', `${errorOpenOccurrences} open occurrences`);

        setText('summaryTasks', tasksPending + tasksRunning);
        setText('summaryTasksMeta', `${tasksPending} pending / ${tasksRunning} running`);

        setText('summaryInfra', nodesOnline);
        setText('summaryInfraMeta', `${workersActive} active workers`);

        setText('projectsMeta', buildMeta('projects', state.projects.length, projectsTotal));
        setText('featuresMeta', buildMeta('features', state.features.length, featuresFilteredTotal));
        setText('bugsMeta', buildMeta('bugs', state.bugs.length, bugsFilteredTotal));
        setText('errorsMeta', buildMeta('errors', state.errors.length, state.errorsTotal));
        setText('pendingTasksMeta', buildMeta('pending', state.pendingTasks.length, tasksPending));
        setText('runningTasksMeta', buildMeta('running', state.runningTasks.length, tasksRunning));
        setText('nodesMeta', buildMeta('nodes', state.nodes.length, nodesTotal));
        const workersTotal = safeNumber(state.workers && state.workers.stats && state.workers.stats.total);
        setText('workersMeta', buildMeta('workers', (state.workers && state.workers.registered_workers ? state.workers.registered_workers.length : 0), workersTotal));
        setText('activityMeta', buildMeta('items', state.activity.length, state.activity.length));
    }

    function buildMeta(label, shown, total) {
        if (total === null || total === undefined || total === 0) {
            return `Showing ${shown} ${label}`;
        }
        if (shown >= total) {
            return `Showing ${shown} ${label}`;
        }
        return `Showing ${shown} of ${total} ${label}`;
    }

    function renderTables() {
        renderTable('projectsTable', 'projectsEmpty', state.projects, [
            { key: 'name' },
            { key: 'priority', mono: true },
            { key: 'feature_count', mono: true },
            { key: 'bug_count', mono: true },
            { key: 'error_count', mono: true }
        ]);

        renderTable('featuresTable', 'featuresEmpty', state.features, [
            { key: 'name' },
            { key: 'project_name' },
            {
                key: 'status',
                render: (row) => createPill(formatStatusLabel(row.status), row.status)
            },
            { key: 'priority', mono: true },
            {
                key: 'created_at',
                render: (row) => formatDate(row.created_at),
                mono: true
            }
        ]);

        renderTable('bugsTable', 'bugsEmpty', state.bugs, [
            { key: 'title' },
            { key: 'project_name' },
            {
                key: 'severity',
                render: (row) => createPill(formatStatusLabel(row.severity), row.severity)
            },
            {
                key: 'status',
                render: (row) => createPill(formatStatusLabel(row.status), row.status)
            },
            {
                key: 'created_at',
                render: (row) => formatDate(row.created_at),
                mono: true
            }
        ]);

        renderTable('errorsTable', 'errorsEmpty', state.errors, [
            {
                key: 'message',
                render: (row) => truncateText(row.message, 48)
            },
            {
                key: 'source',
                render: (row) => truncateText(row.source, 32)
            },
            {
                key: 'status',
                render: (row) => createPill(formatStatusLabel(row.status), row.status)
            },
            { key: 'occurrence_count', mono: true },
            {
                key: 'last_seen',
                render: (row) => formatDateTime(row.last_seen),
                mono: true
            }
        ]);

        renderTable('pendingTasksTable', 'pendingTasksEmpty', state.pendingTasks, [
            { key: 'title', render: (row) => truncateText(row.title, 40) },
            { key: 'task_type' },
            {
                key: 'status',
                render: (row) => createPill(formatStatusLabel(row.status), row.status)
            },
            { key: 'effective_priority', mono: true },
            { key: 'age_minutes', render: (row) => formatAge(row.age_minutes), mono: true }
        ]);

        renderTable('runningTasksTable', 'runningTasksEmpty', state.runningTasks, [
            { key: 'title', render: (row) => truncateText(row.title, 40) },
            { key: 'task_type' },
            {
                key: 'status',
                render: (row) => createPill(formatStatusLabel(row.status), row.status)
            },
            { key: 'effective_priority', mono: true },
            { key: 'age_minutes', render: (row) => formatAge(row.age_minutes), mono: true }
        ]);

        renderTable('nodesTable', 'nodesEmpty', state.nodes, [
            { key: 'hostname' },
            { key: 'role' },
            {
                key: 'status',
                render: (row) => createPill(formatStatusLabel(row.status), row.status)
            },
            { key: 'cpu_usage', render: (row) => formatPercent(row.cpu_usage), mono: true },
            { key: 'memory_usage', render: (row) => formatPercent(row.memory_usage), mono: true },
            { key: 'session_count', mono: true },
            { key: 'worker_count', mono: true }
        ]);

        const workerRows = state.workers && Array.isArray(state.workers.registered_workers)
            ? state.workers.registered_workers
            : [];
        renderTable('workersTable', 'workersEmpty', workerRows, [
            { key: 'id', render: (row) => truncateText(row.id, 20) },
            { key: 'worker_type' },
            {
                key: 'status',
                render: (row) => createPill(formatStatusLabel(row.status), row.status)
            },
            { key: 'node_id', render: (row) => truncateText(row.node_id, 16) },
            { key: 'last_heartbeat', render: (row) => formatDateTime(row.last_heartbeat), mono: true }
        ]);

        renderTable('activityTable', 'activityEmpty', state.activity, [
            { key: 'action' },
            {
                key: 'entity_type',
                render: (row) => `${row.entity_type || '-'} ${row.entity_id || ''}`.trim()
            },
            { key: 'details', render: (row) => truncateText(row.details, 60) },
            { key: 'created_at', render: (row) => formatDateTime(row.created_at), mono: true }
        ]);
    }

    function truncateText(value, maxLen) {
        if (!value) return '-';
        const text = String(value);
        if (text.length <= maxLen) return text;
        return `${text.slice(0, maxLen - 1)}~`;
    }

    function buildSnapshotPayload() {
        return {
            generated_at: state.generatedAt.toISOString(),
            user: document.body.dataset.username || 'User',
            limits: limits,
            stats: state.stats,
            projects: state.projects,
            features: state.features,
            bugs: state.bugs,
            errors: state.errors,
            tasks: {
                pending: state.pendingTasks,
                running: state.runningTasks
            },
            nodes: state.nodes,
            workers: state.workers,
            activity: state.activity
        };
    }

    function downloadSnapshot() {
        const payload = buildSnapshotPayload();
        const timestamp = state.generatedAt.toISOString().replace(/[:.]/g, '').slice(0, 15);
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `dashboard_snapshot_${timestamp}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    async function loadSnapshot() {
        setText('generatedAt', formatDateTime(state.generatedAt));
        setText('generatedAtFooter', formatDateTime(state.generatedAt));
        setText('snapshotNote',
            `Snapshot limits: projects ${limits.projects}, features ${limits.features}, bugs ${limits.bugs}, errors ${limits.errors}, tasks ${limits.pendingTasks} pending and ${limits.runningTasks} running, nodes ${limits.nodes}.`
        );

        const requests = {
            stats: fetchJson('/api/stats'),
            projects: fetchJson(`/api/projects?paginate=true&per_page=${limits.projects}`),
            features: fetchJson(`/api/features?status=in_progress&limit=${limits.features}`),
            bugs: fetchJson(`/api/bugs?status=open&limit=${limits.bugs}`),
            errors: fetchJson(`/api/errors?status=open&limit=${limits.errors}&sort_by=last_seen&sort_order=DESC`),
            pendingTasks: fetchJson(`/api/tasks?status=pending&limit=${limits.pendingTasks}`),
            runningTasks: fetchJson(`/api/tasks?status=running&limit=${limits.runningTasks}`),
            nodes: fetchJson(`/api/nodes?paginate=true&per_page=${limits.nodes}`),
            workers: fetchJson('/api/workers/status')
        };

        const entries = Object.entries(requests);
        const results = await Promise.allSettled(entries.map(([, promise]) => promise));

        const errors = [];
        results.forEach((result, index) => {
            const [key] = entries[index];
            if (result.status === 'fulfilled') {
                const data = result.value;
                switch (key) {
                    case 'stats':
                        state.stats = data;
                        state.activity = Array.isArray(data && data.recent_activity)
                            ? data.recent_activity
                            : [];
                        break;
                    case 'projects':
                        state.projects = normalizeList(data);
                        break;
                    case 'features':
                        state.features = normalizeList(data);
                        break;
                    case 'bugs':
                        state.bugs = normalizeList(data);
                        break;
                    case 'errors':
                        state.errors = normalizeList(data);
                        state.errorsTotal = data && typeof data.total === 'number' ? data.total : null;
                        break;
                    case 'pendingTasks':
                        state.pendingTasks = normalizeList(data);
                        break;
                    case 'runningTasks':
                        state.runningTasks = normalizeList(data);
                        break;
                    case 'nodes':
                        state.nodes = normalizeList(data);
                        break;
                    case 'workers':
                        state.workers = data;
                        break;
                    default:
                        break;
                }
            } else {
                errors.push(`${key} failed`);
            }
        });

        if (errors.length > 0) {
            const errorBanner = getEl('errorBanner');
            if (errorBanner) {
                errorBanner.style.display = 'block';
                errorBanner.textContent = `Some data failed to load: ${errors.join(', ')}.`;
            }
        }

        updateSummary();
        renderTables();
    }

    function bindActions() {
        const printBtn = getEl('printBtn');
        if (printBtn) {
            printBtn.addEventListener('click', () => window.print());
        }

        const exportBtn = getEl('exportJsonBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', downloadSnapshot);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        bindActions();
        loadSnapshot();
    });
})();
