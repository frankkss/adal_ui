/**
 * ADAL Admin - Query Analytics Page JavaScript
 */

// DOM Elements
const searchInput = document.getElementById('search-queries');
const queryTypeFilter = document.getElementById('query-type-filter');
const statusFilter = document.getElementById('status-filter');
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.querySelector('.admin-sidebar');

// State
let allRecentQueries = [];
let allPopularQueries = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadQueryData();
});

function setupEventListeners() {
    // Search input
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterQueries, 300));
    }
    
    // Filters
    if (queryTypeFilter) {
        queryTypeFilter.addEventListener('change', filterQueries);
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', filterQueries);
    }
    
    // Mobile menu toggle
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

async function loadQueryData() {
    try {
        // Load popular queries
        const popularResponse = await fetch('/admin/api/stats/popular?limit=20');
        const popularData = await popularResponse.json();
        
        if (popularResponse.ok) {
            allPopularQueries = popularData;
            renderPopularQueries(popularData);
        }
        
        // Load recent queries
        const recentResponse = await fetch('/admin/api/stats/recent?limit=50');
        const recentData = await recentResponse.json();
        
        if (recentResponse.ok) {
            allRecentQueries = recentData;
            renderRecentQueries(recentData);
        }
    } catch (error) {
        console.error('Error loading query data:', error);
    }
}

function renderPopularQueries(queries) {
    const tbody = document.getElementById('popular-queries-table');
    if (!tbody) return;
    
    if (!queries || queries.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">No popular queries yet</td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = queries.map((q, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(q.query_pattern)}</td>
            <td>
                <span class="category-badge ${q.category || 'other'}">
                    ${q.category || 'other'}
                </span>
            </td>
            <td>${q.count}</td>
            <td>${formatTime(q.last_queried_at)}</td>
        </tr>
    `).join('');
}

function renderRecentQueries(queries) {
    const tbody = document.getElementById('recent-queries-table');
    if (!tbody) return;
    
    if (!queries || queries.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">No recent queries</td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = queries.map(q => `
        <tr>
            <td>${formatTime(q.created_at)}</td>
            <td title="${escapeHtml(q.query_text)}">${escapeHtml(truncate(q.query_text, 60))}</td>
            <td>
                <span class="type-badge ${q.query_type}">
                    ${q.query_type}
                </span>
            </td>
            <td>${q.response_time_ms ? `${q.response_time_ms}ms` : '-'}</td>
            <td>
                <span class="status-badge ${q.was_successful ? 'success' : 'error'}">
                    <i class="fas fa-${q.was_successful ? 'check' : 'times'}"></i>
                    ${q.was_successful ? 'Success' : 'Error'}
                </span>
            </td>
        </tr>
    `).join('');
}

function filterQueries() {
    const searchTerm = searchInput?.value.toLowerCase() || '';
    const queryType = queryTypeFilter?.value || '';
    const status = statusFilter?.value || '';
    
    let filtered = allRecentQueries;
    
    // Search filter
    if (searchTerm) {
        filtered = filtered.filter(q => 
            q.query_text && q.query_text.toLowerCase().includes(searchTerm)
        );
    }
    
    // Type filter
    if (queryType) {
        filtered = filtered.filter(q => q.query_type === queryType);
    }
    
    // Status filter
    if (status === 'success') {
        filtered = filtered.filter(q => q.was_successful);
    } else if (status === 'error') {
        filtered = filtered.filter(q => !q.was_successful);
    }
    
    renderRecentQueries(filtered);
}

// Utility functions
function formatTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = (now - date) / 1000;
    
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function truncate(str, length) {
    if (!str) return '';
    return str.length > length ? str.substring(0, length) + '...' : str;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

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

// Add styles for badges
const style = document.createElement('style');
style.textContent = `
    .category-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: capitalize;
    }
    .category-badge.thesis { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
    .category-badge.academic { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
    .category-badge.library { background: rgba(16, 185, 129, 0.2); color: #10b981; }
    .category-badge.technical { background: rgba(249, 115, 22, 0.2); color: #f97316; }
    .category-badge.general { background: rgba(100, 116, 139, 0.2); color: #64748b; }
    .category-badge.other { background: rgba(100, 116, 139, 0.2); color: #64748b; }
    
    .type-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: capitalize;
    }
    .type-badge.chat { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
    .type-badge.search { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
    
    .empty-state {
        text-align: center;
        color: #64748b;
        padding: 24px;
    }
`;
document.head.appendChild(style);
