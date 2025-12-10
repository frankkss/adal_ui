/**
 * ADAL Admin - Settings Page JavaScript
 */

// DOM Elements
const addAdminBtn = document.getElementById('add-admin-btn');
const addAdminModal = document.getElementById('add-admin-modal');
const closeAddModalBtn = document.getElementById('close-add-modal');
const cancelAddBtn = document.getElementById('cancel-add');
const addAdminForm = document.getElementById('add-admin-form');
const adminsTable = document.getElementById('admins-table');
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.querySelector('.admin-sidebar');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadAdmins();
});

function setupEventListeners() {
    // Add admin button
    if (addAdminBtn) {
        addAdminBtn.addEventListener('click', () => {
            addAdminModal.classList.add('show');
        });
    }
    
    // Close modal
    if (closeAddModalBtn) {
        closeAddModalBtn.addEventListener('click', closeModal);
    }
    
    if (cancelAddBtn) {
        cancelAddBtn.addEventListener('click', closeModal);
    }
    
    if (addAdminModal) {
        addAdminModal.addEventListener('click', (e) => {
            if (e.target === addAdminModal) closeModal();
        });
    }
    
    // Add admin form
    if (addAdminForm) {
        addAdminForm.addEventListener('submit', handleAddAdmin);
    }
    
    // Mobile menu toggle
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
}

async function loadAdmins() {
    try {
        const response = await fetch('/admin/api/admins');
        const data = await response.json();
        
        if (response.ok) {
            renderAdmins(data.admins || []);
        } else {
            adminsTable.innerHTML = `
                <tr>
                    <td colspan="4" class="error-state">Failed to load admins</td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading admins:', error);
        adminsTable.innerHTML = `
            <tr>
                <td colspan="4" class="error-state">Error loading admins</td>
            </tr>
        `;
    }
}

function renderAdmins(admins) {
    if (!adminsTable) return;
    
    if (!admins || admins.length === 0) {
        adminsTable.innerHTML = `
            <tr>
                <td colspan="4" class="empty-state">No admins configured</td>
            </tr>
        `;
        return;
    }
    
    adminsTable.innerHTML = admins.map(a => `
        <tr>
            <td>
                <span class="user-id" title="${a.user_id}">
                    ${truncateId(a.user_id)}
                </span>
            </td>
            <td>
                <span class="role-badge ${a.role}">
                    ${a.role === 'super_admin' ? 'Super Admin' : 'Admin'}
                </span>
            </td>
            <td>${formatDate(a.created_at)}</td>
            <td>
                <button class="btn-action danger" onclick="removeAdmin('${a.user_id}')" title="Remove Admin">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

async function handleAddAdmin(e) {
    e.preventDefault();
    
    const userIdInput = document.getElementById('user-id-input');
    const roleSelect = document.getElementById('role-select');
    
    const userId = userIdInput?.value.trim();
    const role = roleSelect?.value || 'admin';
    
    if (!userId) {
        alert('Please enter a user ID');
        return;
    }
    
    // Validate UUID format
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(userId)) {
        alert('Please enter a valid UUID');
        return;
    }
    
    try {
        const response = await fetch('/admin/api/admins', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ user_id: userId, role: role })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            closeModal();
            loadAdmins();
            userIdInput.value = '';
        } else {
            alert(data.error || 'Failed to add admin');
        }
    } catch (error) {
        console.error('Error adding admin:', error);
        alert('Error adding admin');
    }
}

async function removeAdmin(userId) {
    if (!confirm('Are you sure you want to remove this admin?')) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/admins/${userId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            loadAdmins();
        } else {
            alert(data.error || 'Failed to remove admin');
        }
    } catch (error) {
        console.error('Error removing admin:', error);
        alert('Error removing admin');
    }
}

function closeModal() {
    if (addAdminModal) {
        addAdminModal.classList.remove('show');
    }
}

// Utility functions
function truncateId(id) {
    if (!id) return '';
    return id.length > 12 ? `${id.substring(0, 8)}...${id.substring(id.length - 4)}` : id;
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric',
        year: 'numeric'
    });
}

// Make removeAdmin globally accessible
window.removeAdmin = removeAdmin;

// Add styles
const style = document.createElement('style');
style.textContent = `
    .user-id {
        font-family: monospace;
        font-size: 0.8rem;
        color: #94a3b8;
    }
    
    .role-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .role-badge.admin {
        background: rgba(59, 130, 246, 0.2);
        color: #3b82f6;
    }
    
    .role-badge.super_admin {
        background: rgba(139, 92, 246, 0.2);
        color: #8b5cf6;
    }
    
    .btn-action.danger:hover {
        color: #ef4444;
    }
    
    .empty-state, .error-state {
        text-align: center;
        color: #64748b;
        padding: 24px;
    }
    
    .error-state {
        color: #ef4444;
    }
`;
document.head.appendChild(style);
