const API = 'http://127.0.0.1:8000/api';

function getToken() {
    return localStorage.getItem('token');
}

function getUser() {
    const u = localStorage.getItem('user');
    return u ? JSON.parse(u) : null;
}

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
    toast.textContent = msg;
    toast.className = `toast ${type} show`;
    setTimeout(() => toast.className = 'toast', 3000);
}

async function apiFetch(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(API + endpoint, opts);
    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.detail || 'Something went wrong');
    }
    return data;
}

function setupNavbar() {
    const user = getUser();
    if (!user) return;

    const userInfo = document.getElementById('user-info');
    if (userInfo) {
        userInfo.innerHTML = `
            <span>${user.name} 
                <span class="badge badge-${user.role}">${user.role}</span>
            </span>
            <button class="btn-logout" onclick="logout()">Logout</button>
        `;
    }

    // Hide admin-only elements for members
    if (user.role !== 'admin') {
        document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
    }
}

function requireAuth() {
    if (!getToken()) {
        window.location.href = '/index.html';
    }
}

function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}