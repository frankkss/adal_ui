/**
 * ADAL Admin - User Management Page JavaScript
 */

// DOM Elements
const searchInput = document.getElementById('search-users');
const usersTable = document.getElementById('users-table');
const prevPageBtn = document.getElementById('prev-page');
const nextPageBtn = document.getElementById('next-page');
const pageInfo = document.getElementById('page-info');
const paginationInfo = document.getElementById('pagination-info');
const userModal = document.getElementById('user-modal');
const closeModalBtn = document.getElementById('close-modal');
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.querySelector('.admin-sidebar');

// State
let currentPage = 1;
let totalUsers = 0;
let perPage = 50;
let allUsers = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadUserStats();
    loadUsers();
});

function setupEventListeners() {
    // Search input
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterUsers, 300));
    }
    
    // Pagination
    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                loadUsers();
            }
        });
    }
    
    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', () => {
            if (currentPage * perPage < totalUsers) {
                currentPage++;
                loadUsers();
            }
        });
    }
    
    // Modal close
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }
    
    if (userModal) {
        userModal.addEventListener('click', (e) => {
            if (e.target === userModal) closeModal();
        });
    }
    
    // Mobile menu toggle
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

async function loadUserStats() {
    try {
        const response = await fetch('/admin/api/stats?days=30');
        const data = await response.json();
        
        if (response.ok && data.user_activity) {
            // Total users (approximate from data)
            const totalUsersEl = document.getElementById('total-users');
            if (totalUsersEl && data.summary) {
                totalUsersEl.textContent = data.summary.unique_users || '--';
            }
            
            // Power users
            const powerUsersEl = document.getElementById('power-users');
            if (powerUsersEl) {
                powerUsersEl.textContent = data.user_activity.power_users || 0;
            }
            
            // Avg queries per user
            const avgQueriesEl = document.getElementById('avg-queries');
            if (avgQueriesEl) {
                avgQueriesEl.textContent = data.user_activity.avg_queries_per_user || 0;
            }
        }
    } catch (error) {
        console.error('Error loading user stats:', error);
    }
}

async function loadUsers() {
    try {
        const response = await fetch(`/admin/api/users?page=${currentPage}&per_page=${perPage}`);
        const data = await response.json();
        
        if (response.ok) {
            allUsers = data.users || [];
            totalUsers = data.total || 0;
            renderUsers(allUsers);
            updatePagination();
        }
    } catch (error) {
        console.error('Error loading users:', error);
        usersTable.innerHTML = `
            <tr>
                <td colspan="4" class="error-state">Error loading users</td>
            </tr>
        `;
    }
}

function renderUsers(users) {
    if (!usersTable) return;
    
    if (!users || users.length === 0) {
        usersTable.innerHTML = `
            <tr>
                <td colspan="4" class="empty-state">No users found</td>
            </tr>
        `;
        return;
    }
    
    usersTable.innerHTML = users.map(u => `
        <tr>
            <td>
                <span class="user-id" title="${u.user_id}">
                    ${truncateId(u.user_id)}
                </span>
            </td>
            <td>${u.session_count}</td>
            <td>${u.query_count}</td>
            <td>
                <button class="btn-action" onclick="viewUserDetails('${u.user_id}')" title="View Details">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

function filterUsers() {
    const searchTerm = searchInput?.value.toLowerCase() || '';
    
    if (!searchTerm) {
        renderUsers(allUsers);
        return;
    }
    
    const filtered = allUsers.filter(u => 
        u.user_id.toLowerCase().includes(searchTerm)
    );
    
    renderUsers(filtered);
}

function updatePagination() {
    const start = (currentPage - 1) * perPage + 1;
    const end = Math.min(currentPage * perPage, totalUsers);
    
    if (paginationInfo) {
        paginationInfo.textContent = `Showing ${start}-${end} of ${totalUsers}`;
    }
    
    if (pageInfo) {
        pageInfo.textContent = `Page ${currentPage}`;
    }
    
    if (prevPageBtn) {
        prevPageBtn.disabled = currentPage <= 1;
    }
    
    if (nextPageBtn) {
        nextPageBtn.disabled = currentPage * perPage >= totalUsers;
    }
}

async function viewUserDetails(userId) {
    if (!userModal) return;
    
    const detailsContainer = document.getElementById('user-details');
    detailsContainer.innerHTML = '<div class="loading">Loading...</div>';
    userModal.classList.add('show');
    
    try {
        const response = await fetch(`/admin/api/users/${userId}`);
        const data = await response.json();
        
        if (response.ok) {
            renderUserDetails(data);
        } else {
            detailsContainer.innerHTML = '<div class="error-state">Failed to load user details</div>';
        }
    } catch (error) {
        console.error('Error loading user details:', error);
        detailsContainer.innerHTML = '<div class="error-state">Error loading user details</div>';
    }
}

function renderUserDetails(data) {
    const detailsContainer = document.getElementById('user-details');
    if (!detailsContainer) return;
    
    detailsContainer.innerHTML = `
        <div class="user-detail-header">
            <div class="detail-item">
                <span class="detail-label">User ID</span>
                <span class="detail-value">${data.user_id}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Total Queries</span>
                <span class="detail-value">${data.total_queries}</span>
            </div>
        </div>
        
        <h4>Recent Sessions</h4>
        <div class="sessions-list">
            ${data.recent_sessions && data.recent_sessions.length > 0 ? 
                data.recent_sessions.map(s => `
                    <div class="session-item">
                        <span class="session-title">${escapeHtml(s.title)}</span>
                        <span class="session-date">${formatTime(s.updated_at)}</span>
                    </div>
                `).join('') 
                : '<p class="empty-state">No sessions</p>'
            }
        </div>
        
        <h4>Recent Queries</h4>
        <div class="queries-list">
            ${data.recent_queries && data.recent_queries.length > 0 ? 
                data.recent_queries.map(q => `
                    <div class="query-item">
                        <span class="query-text">${escapeHtml(truncate(q.query_text, 80))}</span>
                        <span class="query-meta">
                            <span class="status-badge ${q.was_successful ? 'success' : 'error'}">
                                ${q.was_successful ? 'Success' : 'Error'}
                            </span>
                            ${formatTime(q.created_at)}
                        </span>
                    </div>
                `).join('') 
                : '<p class="empty-state">No queries</p>'
            }
        </div>
    `;
}

function closeModal() {
    if (userModal) {
        userModal.classList.remove('show');
    }
}

// Utility functions
function truncateId(id) {
    if (!id) return '';
    return id.length > 12 ? `${id.substring(0, 8)}...${id.substring(id.length - 4)}` : id;
}

function truncate(str, length) {
    if (!str) return '';
    return str.length > length ? str.substring(0, length) + '...' : str;
}

function formatTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: 'numeric'
    });
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

// Make viewUserDetails globally accessible
window.viewUserDetails = viewUserDetails;

// Add styles
const style = document.createElement('style');
style.textContent = `
    .user-id {
        font-family: monospace;
        font-size: 0.8rem;
        color: #94a3b8;
    }
    
    .empty-state, .error-state {
        text-align: center;
        color: #64748b;
        padding: 24px;
    }
    
    .error-state {
        color: #ef4444;
    }
    
    .loading {
        text-align: center;
        color: #94a3b8;
        padding: 24px;
    }
    
    .user-detail-header {
        display: flex;
        gap: 24px;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid #374151;
    }
    
    .detail-item {
        display: flex;
        flex-direction: column;
    }
    
    .detail-label {
        font-size: 0.75rem;
        color: #64748b;
        margin-bottom: 4px;
    }
    
    .detail-value {
        font-size: 0.875rem;
        color: #f8fafc;
        font-weight: 500;
    }
    
    #user-details h4 {
        font-size: 0.875rem;
        color: #94a3b8;
        margin: 16px 0 8px;
    }
    
    .sessions-list, .queries-list {
        max-height: 150px;
        overflow-y: auto;
    }
    
    .session-item, .query-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #374151;
    }
    
    .session-title, .query-text {
        font-size: 0.875rem;
        color: #f8fafc;
        flex: 1;
    }
    
    .session-date, .query-meta {
        font-size: 0.75rem;
        color: #64748b;
        display: flex;
        align-items: center;
        gap: 8px;
    }
`;
document.head.appendChild(style);
