// static/js/config.js
const API_BASE_URL = "http://localhost:8000";
const WS_BASE_URL = "ws://localhost:8000";

// 简单的 Token 管理
const auth = {
    setToken: (token) => localStorage.setItem('zju_token', token),
    getToken: () => localStorage.getItem('zju_token'),
    clearToken: () => localStorage.removeItem('zju_token'),
    setCustomLLM: (model, apiKey) => {
        if (model) sessionStorage.setItem('zju_llm_model', model);
        if (apiKey) sessionStorage.setItem('zju_llm_key', apiKey);
    },
    getCustomLLM: () => {
        return {
            model: sessionStorage.getItem('zju_llm_model') || '',
            apiKey: sessionStorage.getItem('zju_llm_key') || ''
        };
    },
    clearCustomLLM: () => {
        sessionStorage.removeItem('zju_llm_model');
        sessionStorage.removeItem('zju_llm_key');
    },
    checkLogin: () => {
        if (!localStorage.getItem('zju_token')) {
            window.location.href = 'index.html';
        }
    }
};