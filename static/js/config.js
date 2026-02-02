// static/js/config.js
const API_BASE_URL = "http://localhost:8000"; 
const WS_BASE_URL = "ws://localhost:8000";

// 简单的 Token 管理
const auth = {
    setToken: (token) => localStorage.setItem('zju_token', token),
    getToken: () => localStorage.getItem('zju_token'),
    clearToken: () => localStorage.removeItem('zju_token'),
    checkLogin: () => {
        if (!localStorage.getItem('zju_token')) {
            window.location.href = 'index.html';
        }
    }
};