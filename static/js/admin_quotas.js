// Admin Quotas Dashboard - JavaScript

const API_BASE = '/api/admin/quotas';
const REFRESH_INTERVAL = 30000; // 30 seconds

let charts = {};
let refreshTimers = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();

    // Set up auto-refresh
    setInterval(loadDashboardData, REFRESH_INTERVAL);
});

// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Deactivate all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName).classList.add('active');

    // Activate button
    event.target.classList.add('active');

    // Load tab-specific data
    if (tabName === 'analytics') {
        loadAnalytics();
    } else if (tabName === 'violations') {
        loadViolations();
    } else if (tabName === 'health') {
        loadSystemHealth();
    }
}

// Load all dashboard data
async function loadDashboardData() {
    try {
        // Load system stats
        const statsResponse = await fetch(`${API_BASE}/status`);
        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            updateSystemStats(stats);
        }

        // Load high utilization users
        const highUtilResponse = await fetch(`${API_BASE}/analytics/high-utilization`);
        if (highUtilResponse.ok) {
            const highUtil = await highUtilResponse.json();
            updateHighUtilizationTable(highUtil.users || []);
        }

        // Load users list
        const usersResponse = await fetch(`${API_BASE}/users`);
        if (usersResponse.ok) {
            const usersData = await usersResponse.json();
            updateUsersTable(usersData.users || []);
        }

        // Load alerts
        const alertsResponse = await fetch(`${API_BASE}/alerts`);
        if (alertsResponse.ok) {
            const alertsData = await alertsResponse.json();
            updateAlertsTable(alertsData.alerts || []);
        }
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

// Update system statistics
function updateSystemStats(stats) {
    // Update stat cards
    setText('total-users', stats.total_users || 0);
    setText('commands-today', formatNumber(stats.total_commands_today || 0));
    setText('system-load', (stats.system_load?.cpu_percent || 0).toFixed(1) + '%');
    setText('throttle-factor', (stats.average_throttle_factor || 1).toFixed(2) + 'x');

    // Update quota status
    if (stats.quota_status) {
        updateQuotaCard('shell', stats.quota_status.shell);
        updateQuotaCard('code', stats.quota_status.code);
        updateQuotaCard('test', stats.quota_status.test);
        updateQuotaCard('review', stats.quota_status.review);
    }
}

// Update quota card
function updateQuotaCard(type, data) {
    if (!data) return;

    const usage = (data.used / data.limit * 100).toFixed(1);
    setText(`${type}-usage`, usage + '%');
    setText(`${type}-detail`, `${data.used} / ${data.limit} (${data.remaining} remaining)`);

    const progress = document.getElementById(`${type}-progress`);
    if (progress) {
        progress.style.width = usage + '%';
        // Change color based on usage
        if (usage > 90) {
            progress.style.background = '#f56565';
        } else if (usage > 80) {
            progress.style.background = '#ed8936';
        } else {
            progress.style.background = 'linear-gradient(90deg, #667eea, #764ba2)';
        }
    }
}

// Update high utilization users table
function updateHighUtilizationTable(users) {
    const tbody = document.getElementById('high-util-tbody');
    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #a0aec0;">No users with high utilization</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(user => `
        <tr>
            <td><strong>${user.username || 'Unknown'}</strong></td>
            <td>${renderProgressBadge(user.daily_utilization || 0)}</td>
            <td>${renderProgressBadge(user.weekly_utilization || 0)}</td>
            <td>${renderProgressBadge(user.monthly_utilization || 0)}</td>
            <td>${getRiskBadge(user.daily_utilization || 0)}</td>
            <td>
                <button class="btn-secondary" onclick="editUser(${user.user_id})">Edit</button>
                <button class="btn-secondary" onclick="resetUserQuota(${user.user_id})">Reset</button>
            </td>
        </tr>
    `).join('');
}

// Update users table
function updateUsersTable(users) {
    const tbody = document.getElementById('users-tbody');
    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #a0aec0;">No users found</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(user => `
        <tr>
            <td><strong>${user.username || 'Unknown'}</strong></td>
            <td><span class="badge badge-info">${user.tier || 'Free'}</span></td>
            <td>${renderProgressBar(user.shell?.daily_percent || 0)}</td>
            <td>${renderProgressBar(user.code?.daily_percent || 0)}</td>
            <td>${renderProgressBar(user.test?.daily_percent || 0)}</td>
            <td>${renderProgressBar(user.overall_usage || 0)}</td>
            <td>
                <button class="btn-secondary" onclick="editUser('${user.user_id}', '${user.username}')">Edit</button>
                <button class="btn-danger" onclick="resetUserQuota('${user.user_id}')">Reset</button>
            </td>
        </tr>
    `).join('');
}

// Update alerts table
function updateAlertsTable(alerts) {
    const tbody = document.getElementById('alerts-tbody');
    if (!alerts || alerts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #a0aec0;">No alerts configured</td></tr>';
        return;
    }

    tbody.innerHTML = alerts.map(alert => `
        <tr>
            <td><strong>${alert.name}</strong></td>
            <td><span class="badge badge-info">${alert.alert_type}</span></td>
            <td>${alert.threshold || '-'}%</td>
            <td>${alert.period || 'daily'}</td>
            <td>${alert.enabled ? '<span class="badge badge-success">Enabled</span>' : '<span class="badge badge-warning">Disabled</span>'}</td>
            <td>${(alert.notification_channels || []).join(', ') || 'None'}</td>
            <td>
                <button class="btn-secondary" onclick="editAlert(${alert.id})">Edit</button>
                <button class="btn-danger" onclick="deleteAlert(${alert.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

// Load analytics data
async function loadAnalytics() {
    try {
        const systemResponse = await fetch(`${API_BASE}/analytics/system`);
        if (systemResponse.ok) {
            const systemData = await systemResponse.json();
            renderCommandDistributionChart(systemData);
            renderCommandTimelineChart(systemData);
        }

        const highUtilResponse = await fetch(`${API_BASE}/analytics/high-utilization`);
        if (highUtilResponse.ok) {
            const highUtil = await highUtilResponse.json();
            renderUserUtilChart(highUtil.users || []);
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Load violations data
async function loadViolations() {
    try {
        const violationsResponse = await fetch(`${API_BASE}/violations`);
        if (violationsResponse.ok) {
            const data = await violationsResponse.json();
            updateViolationsTable(data.violations || []);
        }

        const trendsResponse = await fetch(`${API_BASE}/analytics/violations/trends?days=30`);
        if (trendsResponse.ok) {
            const data = await trendsResponse.json();
            renderViolationTrendChart(data);
        }
    } catch (error) {
        console.error('Error loading violations:', error);
    }
}

// Update violations table
function updateViolationsTable(violations) {
    const tbody = document.getElementById('violations-tbody');
    if (!violations || violations.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #a0aec0;">No violations found</td></tr>';
        return;
    }

    tbody.innerHTML = violations.map(v => `
        <tr>
            <td>${v.username || 'Unknown'}</td>
            <td><span class="badge badge-info">${v.command_type}</span></td>
            <td>${v.quota_exceeded || '-'}</td>
            <td>${v.limit}</td>
            <td>${v.attempted}</td>
            <td>${formatDate(v.violated_at)}</td>
            <td><span class="badge badge-danger">Blocked</span></td>
        </tr>
    `).join('');
}

// Load system health data
async function loadSystemHealth() {
    try {
        const statsResponse = await fetch(`${API_BASE}/status`);
        if (statsResponse.ok) {
            const stats = await statsResponse.json();
            updateSystemHealthCards(stats);
        }
    } catch (error) {
        console.error('Error loading system health:', error);
    }
}

// Update system health cards
function updateSystemHealthCards(stats) {
    const load = stats.system_load || {};

    setText('health-cpu', (load.cpu_percent || 0).toFixed(1) + '%');
    setText('health-mem', (load.memory_percent || 0).toFixed(1) + '%');
    setText('health-db', load.active_connections || 0);
    setText('health-latency', load.p99_response_time || 0);

    // Update health bars
    updateHealthBar('cpu', load.cpu_percent || 0);
    updateHealthBar('mem', load.memory_percent || 0);
}

// Update health bar
function updateHealthBar(type, percent) {
    const bar = document.getElementById(`health-${type}-bar`);
    if (bar) {
        bar.style.width = percent + '%';
        if (percent > 90) {
            bar.style.background = '#f56565';
        } else if (percent > 70) {
            bar.style.background = '#ed8936';
        } else {
            bar.style.background = 'linear-gradient(90deg, #48bb78, #38a169)';
        }
    }
}

// Chart rendering functions
function renderCommandDistributionChart(data) {
    const ctx = document.getElementById('command-dist-chart');
    if (!ctx) return;

    if (charts.commandDist) charts.commandDist.destroy();

    charts.commandDist = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Shell', 'Code', 'Test', 'Review', 'Refactor'],
            datasets: [{
                data: [
                    data.commands_by_type?.shell || 0,
                    data.commands_by_type?.code || 0,
                    data.commands_by_type?.test || 0,
                    data.commands_by_type?.review || 0,
                    data.commands_by_type?.refactor || 0
                ],
                backgroundColor: [
                    '#667eea',
                    '#764ba2',
                    '#f093fb',
                    '#4facfe',
                    '#00f2fe'
                ],
                borderColor: 'white',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function renderCommandTimelineChart(data) {
    const ctx = document.getElementById('command-timeline-chart');
    if (!ctx) return;

    if (charts.timeline) charts.timeline.destroy();

    // Mock data for timeline - would come from real API in production
    const labels = generateDateLabels(7);
    const commandData = Array(7).fill(0).map(() => Math.floor(Math.random() * 1000));

    charts.timeline = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Commands Executed',
                data: commandData,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function renderUserUtilChart(users) {
    const ctx = document.getElementById('user-util-chart');
    if (!ctx) return;

    if (charts.userUtil) charts.userUtil.destroy();

    const topUsers = users.slice(0, 10);

    charts.userUtil = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topUsers.map(u => u.username),
            datasets: [{
                label: 'Daily Utilization %',
                data: topUsers.map(u => u.daily_utilization || 0),
                backgroundColor: topUsers.map(u => {
                    const util = u.daily_utilization || 0;
                    if (util > 90) return '#f56565';
                    if (util > 80) return '#ed8936';
                    return '#48bb78';
                })
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { max: 100 }
            }
        }
    });
}

function renderViolationTrendChart(data) {
    const ctx = document.getElementById('violation-trend-chart');
    if (!ctx) return;

    if (charts.violationTrend) charts.violationTrend.destroy();

    charts.violationTrend = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.trends?.map(t => t.date) || [],
            datasets: [{
                label: 'Daily Violations',
                data: data.trends?.map(t => t.count) || [],
                backgroundColor: '#f56565'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

// User management
function editUser(userId, username) {
    document.getElementById('modalUsername').value = username || userId;
    document.getElementById('userModal').classList.add('active');
}

function closeUserModal() {
    document.getElementById('userModal').classList.remove('active');
}

async function saveUserQuotas(event) {
    event.preventDefault();
    const userId = document.getElementById('modalUsername').value;

    try {
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tier: document.getElementById('modalTier').value,
                custom_limits: {
                    shell: { daily: parseInt(document.getElementById('modalShellDaily').value) || 0 },
                    code: { daily: parseInt(document.getElementById('modalCodeDaily').value) || 0 },
                    test: { daily: parseInt(document.getElementById('modalTestDaily').value) || 0 }
                }
            })
        });

        if (response.ok) {
            showAlert('User quotas updated successfully', 'success');
            closeUserModal();
            loadDashboardData();
        } else {
            showAlert('Error updating user quotas', 'error');
        }
    } catch (error) {
        console.error('Error saving user quotas:', error);
        showAlert('Error updating quotas', 'error');
    }
}

function openUserModal() {
    document.getElementById('modalUsername').value = '';
    document.getElementById('modalTier').value = 'free';
    document.getElementById('userModal').classList.add('active');
}

async function resetUserQuota(userId) {
    if (!confirm('Reset this user\'s quota?')) return;

    try {
        const response = await fetch(`${API_BASE}/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reset_quota: true })
        });

        if (response.ok) {
            showAlert('User quota reset successfully', 'success');
            loadDashboardData();
        }
    } catch (error) {
        console.error('Error resetting quota:', error);
    }
}

// Alert management
function openAlertModal() {
    document.getElementById('alertModal').classList.add('active');
}

function closeAlertModal() {
    document.getElementById('alertModal').classList.remove('active');
}

async function saveAlert(event) {
    event.preventDefault();

    try {
        const response = await fetch(`${API_BASE}/alerts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: document.getElementById('modalAlertName').value,
                alert_type: document.getElementById('modalAlertType').value,
                threshold: parseInt(document.getElementById('modalAlertThreshold').value),
                notify_users: document.getElementById('modalAlertUsers').checked,
                notify_admins: document.getElementById('modalAlertAdmins').checked
            })
        });

        if (response.ok) {
            showAlert('Alert created successfully', 'success');
            closeAlertModal();
            loadDashboardData();
        }
    } catch (error) {
        console.error('Error creating alert:', error);
    }
}

async function deleteAlert(alertId) {
    if (!confirm('Delete this alert?')) return;

    try {
        await fetch(`${API_BASE}/alerts/${alertId}`, { method: 'DELETE' });
        showAlert('Alert deleted', 'success');
        loadDashboardData();
    } catch (error) {
        console.error('Error deleting alert:', error);
    }
}

function editAlert(alertId) {
    // TODO: Implement alert editing
    showAlert('Alert editing not yet implemented', 'info');
}

// Filter users table
function filterUsers() {
    const searchTerm = document.getElementById('user-search').value.toLowerCase();
    const rows = document.querySelectorAll('#users-tbody tr');

    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
}

// Utility functions
function setText(elementId, text) {
    const el = document.getElementById(elementId);
    if (el) el.textContent = text;
}

function formatNumber(num) {
    return new Intl.NumberFormat().format(num);
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function renderProgressBadge(percent) {
    const color = percent > 90 ? '#f56565' : percent > 80 ? '#ed8936' : '#48bb78';
    return `<span style="background: ${color}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: 600;">${percent.toFixed(1)}%</span>`;
}

function renderProgressBar(percent) {
    return `<div style="background: #e2e8f0; height: 6px; border-radius: 3px; overflow: hidden;">
        <div style="background: linear-gradient(90deg, #667eea, #764ba2); height: 100%; width: ${Math.min(percent, 100)}%"></div>
    </div>`;
}

function getRiskBadge(utilization) {
    if (utilization > 95) return '<span class="badge badge-danger">Critical</span>';
    if (utilization > 90) return '<span class="badge badge-danger">High</span>';
    if (utilization > 80) return '<span class="badge badge-warning">Medium</span>';
    return '<span class="badge badge-success">Low</span>';
}

function generateDateLabels(days) {
    const labels = [];
    for (let i = days - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    }
    return labels;
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.style.position = 'fixed';
    alertDiv.style.top = '20px';
    alertDiv.style.right = '20px';
    alertDiv.style.zIndex = '2000';
    alertDiv.style.minWidth = '300px';

    document.body.appendChild(alertDiv);

    setTimeout(() => {
        alertDiv.remove();
    }, 4000);
}
