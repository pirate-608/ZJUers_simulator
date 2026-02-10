document.addEventListener('DOMContentLoaded', function () {
    const now = new Date();
    const dateStr = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`;
    const dateEl = document.getElementById('current-date');
    if (dateEl) dateEl.innerText = dateStr;

    const token = localStorage.getItem('zju_token');
    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    fetch('/api/admission_info', {
        headers: {
            Authorization: 'Bearer ' + token,
        },
    })
        .then((response) => {
            if (!response.ok) throw new Error('接口响应异常');
            return response.json();
        })
        .then((data) => {
            const nameEl = document.getElementById('student-name');
            const majorEl = document.getElementById('student-major');
            if (nameEl) nameEl.innerText = data.username || '新同学';
            if (majorEl) majorEl.innerText = data.assigned_major || '未分配专业';
            if (data.token) {
                const tokenEl = document.getElementById('student-token');
                const box = document.getElementById('token-box');
                if (tokenEl) tokenEl.innerText = data.token;
                if (box) box.style.display = '';
            }
        })
        .catch((error) => {
            console.error('无法获取录取信息:', error);
            const nameEl = document.getElementById('student-name');
            const majorEl = document.getElementById('student-major');
            if (nameEl) nameEl.innerText = '新同学';
            if (majorEl) majorEl.innerText = '数据加载失败';
        });
});
