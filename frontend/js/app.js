const API = '/api';

function getToken() { return localStorage.getItem('token'); }
function getUser()  { const u = localStorage.getItem('user'); return u ? JSON.parse(u) : null; }

function logout() {
    localStorage.clear();
    window.location.href = '/index.html';
}

function showToast(msg, type = 'success') {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || '✓'}</span><span>${msg}</span>`;
    toast.className = `toast ${type} show`;
    setTimeout(() => { toast.className = 'toast'; }, 3500);
}

async function apiFetch(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(API + endpoint, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Something went wrong');
    return data;
}

function setupNavbar() {
    const user = getUser();
    if (!user) return;
    const el = document.getElementById('user-info');
    if (el) {
        const initials = user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0,2);
        el.innerHTML = `
            <div class="user-chip">
                <div class="avatar">${initials}</div>
                <span class="user-name">${user.name}</span>
                <span class="badge badge-${user.role}">${user.role}</span>
            </div>
            <button class="btn-logout" onclick="logout()">Sign out</button>
        `;
    }
    if (user.role !== 'admin') {
        document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
    }
}

function requireAuth() {
    if (!getToken()) window.location.href = '/index.html';
}

function openModal(id)  { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

// Close modal on overlay click
document.addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});
