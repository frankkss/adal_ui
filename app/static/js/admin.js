/**
 * ADAL Admin Dashboard JavaScript
 * Main dashboard functionality with charts and analytics
 */

// Chart instances
let queriesChart = null;
let hourlyChart = null;
let categoriesChart = null;

// DOM Elements
const dateRangeSelect = document.getElementById('date-range');
const refreshBtn = document.getElementById('refresh-btn');
const logoutBtn = document.getElementById('logout-btn');
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.querySelector('.admin-sidebar');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadDashboardData();
});

function setupEventListeners() {
    // Date range filter
    if (dateRangeSelect) {
        dateRangeSelect.addEventListener('change', loadDashboardData);
    }
    
    // Refresh button
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            refreshBtn.classList.add('rotating');
            loadDashboardData().finally(() => {
                setTimeout(() => refreshBtn.classList.remove('rotating'), 500);
            });
        });
    }
    
    // Logout button
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
    // Mobile menu toggle
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

async function loadDashboardData() {
    const days = dateRangeSelect ? parseInt(dateRangeSelect.value) : 30;
    
    try {
        const response = await fetch(`/admin/api/stats?days=${days}`);
        const data = await response.json();
        
        if (response.ok) {
            updateSummaryCards(data.summary);
            updateQueriesChart(data.daily_queries);
            updateHourlyChart(data.hourly_distribution);
            updateCategoriesChart(data.query_categories);
            updatePopularQueries(data.popular_queries);
            updateRecentActivity(data.recent_queries);
        } else {
            console.error('Failed to load dashboard data:', data.error);
            showError('Failed to load dashboard data');
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showError('Error connecting to server');
    }
}

function updateSummaryCards(summary) {
    if (!summary) return;
    
    // Total Queries
    const totalQueries = document.getElementById('total-queries');
    if (totalQueries) {
        animateValue(totalQueries, summary.total_queries || 0);
    }
    
    // Query growth
    const queriesChange = document.getElementById('queries-change');
    if (queriesChange && summary.query_growth_percent !== undefined) {
        const growth = summary.query_growth_percent;
        queriesChange.innerHTML = `
            <i class="fas fa-arrow-${growth >= 0 ? 'up' : 'down'}"></i>
            <span>${Math.abs(growth).toFixed(1)}%</span>
        `;
        queriesChange.className = `stat-change ${growth >= 0 ? 'positive' : 'negative'}`;
    }
    
    // Active Users
    const activeUsers = document.getElementById('active-users');
    if (activeUsers) {
        animateValue(activeUsers, summary.unique_users || 0);
    }
    
    // Total Sessions
    const totalSessions = document.getElementById('total-sessions');
    if (totalSessions) {
        animateValue(totalSessions, summary.total_sessions || 0);
    }
    
    // Average Response Time
    const avgResponse = document.getElementById('avg-response');
    if (avgResponse) {
        const time = summary.avg_response_time_ms || 0;
        avgResponse.textContent = time > 1000 
            ? `${(time / 1000).toFixed(1)}s` 
            : `${Math.round(time)}ms`;
    }
    
    // Success Rate
    const successRate = document.getElementById('success-rate');
    if (successRate) {
        successRate.textContent = `${(summary.success_rate || 100).toFixed(1)}%`;
    }
}

function updateQueriesChart(dailyData) {
    const ctx = document.getElementById('queries-chart');
    if (!ctx) return;
    
    // Ensure we have data
    if (!dailyData || dailyData.length === 0) {
        dailyData = [{ date: new Date().toISOString().split('T')[0], queries: 0, unique_users: 0 }];
    }
    
    const labels = dailyData.map(d => formatDate(d.date));
    const queryData = dailyData.map(d => d.queries);
    const userData = dailyData.map(d => d.unique_users);
    
    // Destroy existing chart completely
    if (queriesChart) {
        queriesChart.destroy();
        queriesChart = null;
    }
    
    queriesChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Queries',
                    data: queryData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Unique Users',
                    data: userData,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 100,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1a1f2e',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#374151',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#374151',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        maxTicksLimit: 7
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#374151',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        precision: 0
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

function updateHourlyChart(hourlyData) {
    const ctx = document.getElementById('hourly-chart');
    if (!ctx) return;
    
    // Ensure we have data for all 24 hours
    if (!hourlyData || hourlyData.length === 0) {
        hourlyData = Array.from({length: 24}, (_, i) => ({ hour: i, count: 0 }));
    }
    
    const labels = hourlyData.map(d => `${d.hour}:00`);
    const data = hourlyData.map(d => d.count);
    
    // Destroy existing chart completely
    if (hourlyChart) {
        hourlyChart.destroy();
        hourlyChart = null;
    }
    
    hourlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Queries',
                data: data,
                backgroundColor: 'rgba(139, 92, 246, 0.6)',
                borderColor: '#8b5cf6',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 100,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#1a1f2e',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8'
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        maxTicksLimit: 12,
                        callback: function(value, index) {
                            return index % 2 === 0 ? this.getLabelForValue(value) : '';
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#374151',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#94a3b8',
                        precision: 0
                    }
                }
            }
        }
    });
}

function updateCategoriesChart(categories) {
    const ctx = document.getElementById('categories-chart');
    if (!ctx) return;
    
    // Validate data
    if (!categories || !Array.isArray(categories) || categories.length === 0) {
        categories = [{ category: 'No Data', count: 1 }];
    }
    
    const labels = categories.map(c => c.category || 'Unknown');
    const data = categories.map(c => parseInt(c.count) || 0);
    
    const colors = [
        '#10b981', '#3b82f6', '#8b5cf6', '#f97316', '#ef4444',
        '#eab308', '#14b8a6', '#ec4899', '#6366f1', '#84cc16'
    ];
    
    // Properly destroy existing chart
    if (categoriesChart) {
        categoriesChart.destroy();
        categoriesChart = null;
    }
    
    categoriesChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: '#252b3b',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 100,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#94a3b8',
                        usePointStyle: true,
                        padding: 12,
                        font: {
                            size: 11
                        }
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1f2e',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8'
                }
            },
            cutout: '60%'
        }
    });
}

function updatePopularQueries(queries) {
    const container = document.getElementById('popular-queries');
    if (!container) return;
    
    if (!queries || queries.length === 0) {
        container.innerHTML = '<li class="empty-state">No trending topics yet</li>';
        return;
    }
    
    container.innerHTML = queries.map(q => `
        <li>
            <span class="trending-topic">
                ${escapeHtml(q.query_pattern)}
                ${q.category ? `<span class="trending-category">${q.category}</span>` : ''}
            </span>
            <span class="trending-count">${q.count} queries</span>
        </li>
    `).join('');
}

function updateRecentActivity(activities) {
    const container = document.getElementById('recent-activity');
    if (!container) return;
    
    if (!activities || activities.length === 0) {
        container.innerHTML = '<li class="empty-state">No recent activity</li>';
        return;
    }
    
    container.innerHTML = activities.slice(0, 10).map(a => `
        <li>
            <div class="activity-icon ${a.was_successful ? 'success' : 'error'}">
                <i class="fas fa-${a.was_successful ? 'comment' : 'exclamation'}"></i>
            </div>
            <div class="activity-content">
                <div class="activity-text">${escapeHtml(a.query_text)}</div>
                <div class="activity-time">${formatTime(a.created_at)}</div>
            </div>
        </li>
    `).join('');
}

// Utility Functions
function animateValue(element, value) {
    const duration = 500;
    const start = parseInt(element.textContent) || 0;
    const range = value - start;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        const currentValue = Math.round(start + range * easeProgress);
        
        element.textContent = currentValue.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = (now - date) / 1000;
    
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} days ago`;
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    console.error(message);
    // You could add a toast notification here
}

async function handleLogout() {
    try {
        await fetch('/api/auth/signout', { method: 'POST' });
        window.location.href = '/login';
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/login';
    }
}

// Add rotating animation for refresh button
const style = document.createElement('style');
style.textContent = `
    .refresh-btn.rotating i {
        animation: spin 0.5s linear infinite;
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .empty-state {
        text-align: center;
        color: #64748b;
        padding: 20px;
    }
`;
document.head.appendChild(style);
