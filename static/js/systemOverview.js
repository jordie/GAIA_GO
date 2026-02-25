/**
 * System Overview Dashboard Component
 * Provides comprehensive view of all systems, sessions, and environments
 */

class SystemOverview {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.refreshInterval = null;
        this.data = null;
    }

    /**
     * Escape HTML to prevent XSS attacks.
     * Uses global Sanitize if available, otherwise falls back to local implementation.
     */
    escapeHtml(str) {
        if (str === null || str === undefined) return '';
        if (typeof window.Sanitize !== 'undefined' && window.Sanitize.escapeHtml) {
            return window.Sanitize.escapeHtml(str);
        }
        // Fallback implementation
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    async fetchData() {
        try {
            const response = await fetch('/api/system/overview');
            if (!response.ok) throw new Error('Failed to fetch system overview');
            this.data = await response.json();
            return this.data;
        } catch (error) {
            console.error('SystemOverview fetch error:', error);
            return null;
        }
    }

    async fetchDecisionData() {
        try {
            const response = await fetch('/api/system/decision-data');
            if (!response.ok) throw new Error('Failed to fetch decision data');
            return await response.json();
        } catch (error) {
            console.error('Decision data fetch error:', error);
            return null;
        }
    }

    formatUptime(seconds) {
        if (!seconds) return '-';
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        if (hours > 24) {
            const days = Math.floor(hours / 24);
            return `${days}d ${hours % 24}h`;
        }
        return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
    }

    getStatusColor(status) {
        const colors = {
            'online': '#28a745',
            'offline': '#dc3545',
            'working': '#28a745',
            'thinking': '#17a2b8',
            'idle': '#ffc107',
            'unknown': '#6c757d',
            'ok': '#28a745',
            'locked': '#dc3545',
            'error': '#dc3545',
        };
        return colors[status] || '#6c757d';
    }

    getStatusIcon(status) {
        const icons = {
            'online': '●',
            'offline': '○',
            'working': '⚙️',
            'thinking': '🧠',
            'idle': '💤',
            'unknown': '❓',
        };
        return icons[status] || '•';
    }

    renderSummaryCards() {
        if (!this.data) return '';

        const s = this.data.summary;
        return `
            <div class="overview-summary">
                <div class="summary-card">
                    <div class="summary-value">${s.services_running}/${s.services_running + s.services_stopped}</div>
                    <div class="summary-label">Services Online</div>
                    <div class="summary-bar">
                        <div class="bar-fill" style="width: ${(s.services_running / (s.services_running + s.services_stopped)) * 100}%; background: #28a745;"></div>
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">${s.sessions_working}/${s.sessions_total}</div>
                    <div class="summary-label">Sessions Working</div>
                    <div class="summary-bar">
                        <div class="bar-fill" style="width: ${(s.sessions_working / s.sessions_total) * 100}%; background: #17a2b8;"></div>
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">${s.cpu_percent}%</div>
                    <div class="summary-label">CPU Usage</div>
                    <div class="summary-bar">
                        <div class="bar-fill" style="width: ${s.cpu_percent}%; background: ${s.cpu_percent > 80 ? '#dc3545' : '#28a745'};"></div>
                    </div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">${s.memory_percent}%</div>
                    <div class="summary-label">Memory Usage</div>
                    <div class="summary-bar">
                        <div class="bar-fill" style="width: ${s.memory_percent}%; background: ${s.memory_percent > 85 ? '#dc3545' : '#28a745'};"></div>
                    </div>
                </div>
            </div>
        `;
    }

    renderServicesMatrix() {
        if (!this.data) return '';

        let html = '<div class="services-matrix">';

        for (const [project, envs] of Object.entries(this.data.services)) {
            html += `<div class="project-group">
                <h4 class="project-title">${this.escapeHtml(project.toUpperCase())}</h4>
                <div class="env-grid">`;

            for (const [env, info] of Object.entries(envs)) {
                const status = info.running ? 'online' : 'offline';
                const uptime = info.process ? this.formatUptime(info.process.uptime_seconds) : '-';
                const mem = info.process ? `${info.process.memory_mb.toFixed(0)}MB` : '-';

                html += `
                    <div class="env-card ${this.escapeHtml(status)}">
                        <div class="env-status" style="color: ${this.getStatusColor(status)}">
                            ${this.getStatusIcon(status)}
                        </div>
                        <div class="env-name">${this.escapeHtml(env)}</div>
                        <div class="env-port">:${this.escapeHtml(String(info.port))}</div>
                        <div class="env-metrics">
                            <span title="Uptime">⏱ ${this.escapeHtml(uptime)}</span>
                            <span title="Memory">💾 ${this.escapeHtml(mem)}</span>
                        </div>
                    </div>
                `;
            }

            html += '</div></div>';
        }

        html += '</div>';
        return html;
    }

    renderSessionsPanel() {
        if (!this.data) return '';

        const sessions = Object.entries(this.data.sessions);
        const byProject = {};

        // Group by project
        for (const [name, info] of sessions) {
            const project = info.project || 'unassigned';
            if (!byProject[project]) byProject[project] = [];
            byProject[project].push({ name, ...info });
        }

        let html = '<div class="sessions-panel">';

        for (const [project, items] of Object.entries(byProject)) {
            html += `<div class="session-group">
                <h4 class="group-title">${this.escapeHtml(project.toUpperCase())} (${items.length})</h4>
                <div class="session-list">`;

            for (const session of items) {
                const stateColor = this.getStatusColor(session.state);
                const stateIcon = this.getStatusIcon(session.state);
                const safeState = this.escapeHtml(session.state);
                const safeName = this.escapeHtml(session.name);
                const safeTask = session.task ? this.escapeHtml(session.task) : '';
                const safeTaskPreview = session.task ? this.escapeHtml(session.task.substring(0, 30)) : '';

                html += `
                    <div class="session-row ${safeState}">
                        <span class="session-icon" style="color: ${stateColor}">${stateIcon}</span>
                        <span class="session-name">${safeName}</span>
                        <span class="session-state">${safeState}</span>
                        ${session.task ? `<span class="session-task" title="${safeTask}">${safeTaskPreview}...</span>` : ''}
                    </div>
                `;
            }

            html += '</div></div>';
        }

        html += '</div>';
        return html;
    }

    renderAlertsPanel(decisionData) {
        if (!decisionData) return '';

        let html = '<div class="alerts-panel">';

        // Alerts
        if (decisionData.alerts && decisionData.alerts.length > 0) {
            html += '<div class="alerts-section"><h4>⚠️ Alerts</h4>';
            for (const alert of decisionData.alerts) {
                const color = alert.level === 'critical' ? '#dc3545' : '#ffc107';
                html += `
                    <div class="alert-item" style="border-left: 3px solid ${color}">
                        <div class="alert-message">${this.escapeHtml(alert.message)}</div>
                        <div class="alert-action">→ ${this.escapeHtml(alert.action)}</div>
                    </div>
                `;
            }
            html += '</div>';
        }

        // Recommendations
        if (decisionData.recommendations && decisionData.recommendations.length > 0) {
            html += '<div class="recommendations-section"><h4>💡 Recommendations</h4>';
            for (const rec of decisionData.recommendations) {
                html += `
                    <div class="recommendation-item">
                        <div class="rec-message">${this.escapeHtml(rec.message)}</div>
                        <div class="rec-action">→ ${this.escapeHtml(rec.action)}</div>
                    </div>
                `;
            }
            html += '</div>';
        }

        html += '</div>';
        return html;
    }

    renderDatabasesPanel() {
        if (!this.data) return '';

        let html = '<div class="databases-panel"><h4>🗄️ Databases</h4><div class="db-grid">';

        for (const [name, info] of Object.entries(this.data.databases)) {
            const statusColor = this.getStatusColor(info.status);
            html += `
                <div class="db-card">
                    <div class="db-status" style="color: ${statusColor}">●</div>
                    <div class="db-name">${this.escapeHtml(name)}</div>
                    <div class="db-size">${this.escapeHtml(String(info.size_mb))} MB</div>
                    <div class="db-state">${this.escapeHtml(info.status)}</div>
                </div>
            `;
        }

        html += '</div></div>';
        return html;
    }

    async render() {
        if (!this.container) return;

        await this.fetchData();
        const decisionData = await this.fetchDecisionData();

        if (!this.data) {
            this.container.innerHTML = '<div class="error">Failed to load system overview</div>';
            return;
        }

        this.container.innerHTML = `
            <div class="system-overview">
                <div class="overview-header">
                    <h2>System Overview</h2>
                    <span class="last-update">Updated: ${new Date(this.data.timestamp).toLocaleTimeString()}</span>
                    <button onclick="systemOverview.render()" class="refresh-btn">🔄 Refresh</button>
                </div>

                ${this.renderSummaryCards()}

                <div class="overview-grid">
                    <div class="overview-section services-section">
                        <h3>🖥️ Services</h3>
                        ${this.renderServicesMatrix()}
                    </div>

                    <div class="overview-section sessions-section">
                        <h3>🤖 Claude Sessions</h3>
                        ${this.renderSessionsPanel()}
                    </div>

                    <div class="overview-section alerts-section">
                        <h3>📊 Decision Support</h3>
                        ${this.renderAlertsPanel(decisionData)}
                        ${this.renderDatabasesPanel()}
                    </div>
                </div>
            </div>
        `;
    }

    startAutoRefresh(intervalMs = 30000) {
        this.stopAutoRefresh();
        this.refreshInterval = setInterval(() => this.render(), intervalMs);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
}

// CSS Styles
const overviewStyles = `
<style>
.system-overview {
    padding: 1rem;
    background: var(--bg-primary, #1a1a2e);
    color: var(--text-primary, #e0e0e0);
}

.overview-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color, #333);
}

.overview-header h2 {
    margin: 0;
    flex-grow: 1;
}

.last-update {
    font-size: 0.85rem;
    color: var(--text-secondary, #888);
}

.refresh-btn {
    padding: 0.5rem 1rem;
    background: var(--accent-color, #4a90d9);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
}

.refresh-btn:hover {
    opacity: 0.9;
}

.overview-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.summary-card {
    background: var(--bg-secondary, #252540);
    padding: 1rem;
    border-radius: 8px;
    text-align: center;
}

.summary-value {
    font-size: 1.8rem;
    font-weight: bold;
    color: var(--accent-color, #4a90d9);
}

.summary-label {
    font-size: 0.85rem;
    color: var(--text-secondary, #888);
    margin: 0.25rem 0;
}

.summary-bar {
    height: 4px;
    background: var(--bg-tertiary, #333);
    border-radius: 2px;
    overflow: hidden;
    margin-top: 0.5rem;
}

.bar-fill {
    height: 100%;
    transition: width 0.3s ease;
}

.overview-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1rem;
}

@media (max-width: 1400px) {
    .overview-grid {
        grid-template-columns: 1fr 1fr;
    }
}

@media (max-width: 900px) {
    .overview-grid {
        grid-template-columns: 1fr;
    }
}

.overview-section {
    background: var(--bg-secondary, #252540);
    border-radius: 8px;
    padding: 1rem;
}

.overview-section h3 {
    margin: 0 0 1rem 0;
    font-size: 1.1rem;
    border-bottom: 1px solid var(--border-color, #333);
    padding-bottom: 0.5rem;
}

/* Services Matrix */
.services-matrix {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.project-group {
    margin-bottom: 0.5rem;
}

.project-title {
    font-size: 0.9rem;
    color: var(--text-secondary, #888);
    margin: 0 0 0.5rem 0;
}

.env-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
    gap: 0.5rem;
}

.env-card {
    background: var(--bg-tertiary, #333);
    padding: 0.5rem;
    border-radius: 4px;
    text-align: center;
    font-size: 0.8rem;
}

.env-card.online {
    border-left: 3px solid #28a745;
}

.env-card.offline {
    border-left: 3px solid #dc3545;
    opacity: 0.7;
}

.env-status {
    font-size: 1rem;
}

.env-name {
    font-weight: bold;
    margin: 0.25rem 0;
}

.env-port {
    color: var(--text-secondary, #888);
    font-size: 0.75rem;
}

.env-metrics {
    font-size: 0.7rem;
    color: var(--text-secondary, #888);
    margin-top: 0.25rem;
}

.env-metrics span {
    margin-right: 0.5rem;
}

/* Sessions Panel */
.sessions-panel {
    max-height: 400px;
    overflow-y: auto;
}

.session-group {
    margin-bottom: 1rem;
}

.group-title {
    font-size: 0.85rem;
    color: var(--accent-color, #4a90d9);
    margin: 0 0 0.5rem 0;
}

.session-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.session-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.5rem;
    background: var(--bg-tertiary, #333);
    border-radius: 4px;
    font-size: 0.8rem;
}

.session-row.working, .session-row.thinking {
    background: rgba(40, 167, 69, 0.1);
}

.session-row.idle {
    opacity: 0.7;
}

.session-icon {
    font-size: 0.9rem;
}

.session-name {
    font-weight: 500;
    min-width: 100px;
}

.session-state {
    color: var(--text-secondary, #888);
    font-size: 0.75rem;
}

.session-task {
    color: var(--text-secondary, #888);
    font-size: 0.75rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 150px;
}

/* Alerts Panel */
.alerts-panel {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.alerts-section h4, .recommendations-section h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
}

.alert-item, .recommendation-item {
    background: var(--bg-tertiary, #333);
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

.alert-message, .rec-message {
    font-size: 0.85rem;
    margin-bottom: 0.25rem;
}

.alert-action, .rec-action {
    font-size: 0.8rem;
    color: var(--text-secondary, #888);
}

/* Databases Panel */
.databases-panel {
    margin-top: 1rem;
}

.databases-panel h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
}

.db-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 0.5rem;
}

.db-card {
    background: var(--bg-tertiary, #333);
    padding: 0.5rem;
    border-radius: 4px;
    text-align: center;
    font-size: 0.8rem;
}

.db-status {
    font-size: 1rem;
}

.db-name {
    font-weight: 500;
    margin: 0.25rem 0;
}

.db-size, .db-state {
    font-size: 0.75rem;
    color: var(--text-secondary, #888);
}
</style>
`;

// Inject styles
if (!document.getElementById('system-overview-styles')) {
    const styleDiv = document.createElement('div');
    styleDiv.id = 'system-overview-styles';
    styleDiv.innerHTML = overviewStyles;
    document.head.appendChild(styleDiv.firstElementChild);
}

// Global instance
let systemOverview = null;

// Initialize when DOM is ready
function initSystemOverview(containerId = 'system-overview-container') {
    systemOverview = new SystemOverview(containerId);
    systemOverview.render();
    systemOverview.startAutoRefresh(30000);
    return systemOverview;
}
