// static/js/exam.js
let currentUser = "";

// startExam 修改为 async 函数，因为要请求网络
async function startExam() {
    const username = document.getElementById('username').value.trim();
    if (!username) return alert("请先填写姓名");
    currentUser = username;

    // 切换 UI 到加载状态（防止网络慢的时候用户乱点）
    const loginDiv = document.getElementById('step-login');
    const btn = loginDiv.querySelector('button');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "正在抽取题库...";

    try {
        // 1. 请求后端获取题目
        const response = await fetch(`${API_BASE_URL}/api/exam/questions`);
        if (!response.ok) throw new Error("获取题目失败");
        
        const questions = await response.json();

        // 2. 渲染题目
        const container = document.getElementById('questions-container');
        container.innerHTML = questions.map(q => `
            <div class="mb-4">
                <label class="form-label fw-bold">
                    <span class="badge bg-primary me-2">${q.score}分</span>${q.content}
                </label>
                <input type="text" class="form-control" name="${q.id}" autocomplete="off" placeholder="请输入答案...">
            </div>
        `).join('');

        // 3. 切换显示
        document.getElementById('step-login').style.display = 'none';
        document.getElementById('step-exam').style.display = 'block';

    } catch (error) {
        console.error(error);
        alert("题库加载失败，请检查网络或后端服务");
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

async function submitExam() {
    // 收集答案
    const form = document.getElementById('exam-form');
    const formData = new FormData(form);
    const answers = {};
    formData.forEach((value, key) => {
        answers[key] = value;
    });

    // UI切换
    document.getElementById('step-exam').style.display = 'none';
    document.getElementById('step-loading').style.display = 'block';

    try {
        const response = await fetch(`${API_BASE_URL}/api/exam/submit`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: currentUser,
                answers: answers
            })
        });

        const result = await response.json();
        
        // 显示结果
        document.getElementById('step-loading').style.display = 'none';
        const modalBody = document.getElementById('result-body');
        const modalEl = new bootstrap.Modal(document.getElementById('resultModal'), {backdrop: 'static'});

        if (result.status === 'success') {
            auth.setToken(result.token); // 保存 Token
            modalBody.innerHTML = `
                <div class="text-center text-success">
                    <h4>🎉 恭喜录取!</h4>
                    <p>得分: ${result.score}</p>
                    <p>你的专业档位: <strong>${result.tier}</strong></p>
                </div>
            `;
            modalEl.show();
        } else {
            modalBody.innerHTML = `
                <div class="text-center text-danger">
                    <h4>😭 遗憾离场</h4>
                    <p>得分: ${result.score}</p>
                    <p>距离分数线还差一点点...</p>
                </div>
            `;
            // 修改按钮行为为刷新
            document.querySelector('#resultModal .btn-primary').textContent = "重新考试";
            document.querySelector('#resultModal .btn-primary').onclick = () => location.reload();
            modalEl.show();
        }

    } catch (error) {
        alert("网络连接失败，请检查后端服务");
        console.error(error);
        location.reload();
    }
}

function goToGame() {
    window.location.href = 'dashboard.html';
}