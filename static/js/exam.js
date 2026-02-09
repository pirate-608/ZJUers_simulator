// 老玩家快速报到，无需考试
async function quickLogin() {
    const username = document.getElementById('username').value.trim();
    const token = document.getElementById('token').value.trim();
    if (!username) return alert("请先填写姓名");
    currentUser = username;
    const btns = document.querySelectorAll('#step-login button');
    btns.forEach(btn => btn.disabled = true);
    try {
        const payload = token ? { username, token } : { username };
        const llm = collectCustomLlm();
        Object.assign(payload, llm);
        auth.setCustomLLM(llm.custom_llm_model, llm.custom_llm_api_key);
        const response = await fetch(`${API_BASE_URL}/api/exam/quick_login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.status === 'success' && result.token) {
            auth.setToken(result.token);
            window.location.href = '/admission';
        } else {
            alert(result.message || '未找到该用户，请先完成入学考试');
            btns.forEach(btn => btn.disabled = false);
        }
    } catch (e) {
        alert('网络异常，请重试');
        btns.forEach(btn => btn.disabled = false);
    }
}
// static/js/exam.js
let currentUser = "";

function collectCustomLlm() {
    const toggle = document.getElementById('custom-llm-toggle');
    if (!toggle || !toggle.checked) return {};
    const model = document.getElementById('custom-llm-model')?.value.trim();
    const apiKey = document.getElementById('custom-llm-key')?.value.trim();
    const result = {};
    if (model) result.custom_llm_model = model;
    if (apiKey) result.custom_llm_api_key = apiKey;
    return result;
}

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

    // 读取 token（如果有）
    const token = document.getElementById('token').value.trim();

    // UI切换
    document.getElementById('step-exam').style.display = 'none';
    document.getElementById('step-loading').style.display = 'block';

    try {
        const payload = {
            username: currentUser,
            answers: answers
        };
        if (token) payload.token = token;
        const llm = collectCustomLlm();
        Object.assign(payload, llm);
        auth.setCustomLLM(llm.custom_llm_model, llm.custom_llm_api_key);

        const response = await fetch(`${API_BASE_URL}/api/exam/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        console.log('考试提交结果:', result); // 调试日志

        // 显示结果
        document.getElementById('step-loading').style.display = 'none';
        const modalBody = document.getElementById('result-body');
        const modalEl = new bootstrap.Modal(document.getElementById('resultModal'), { backdrop: 'static' });

        if (result.status === 'success') {
            auth.setToken(result.token); // 保存 Token
            // 1. 调用分配专业API
            await assignMajorWithAnimation(result.token);
        } else if (result.status === 'error') {
            // 处理用户名重复等业务错误
            modalBody.innerHTML = `
                <div class="text-center text-warning">
                    <h4>⚠️ ${result.message}</h4>
                    <p class="text-muted small mt-3">提示：如果是老玩家，请填写学生凭证后使用"直接报到"功能</p>
                </div>
            `;
            document.querySelector('#resultModal .btn-primary').textContent = "返回重试";
            document.querySelector('#resultModal .btn-primary').onclick = () => location.reload();
            modalEl.show();
        } else {
            // 考试失败
            const scoreDisplay = result.score !== null && result.score !== undefined
                ? result.score
                : '0';
            modalBody.innerHTML = `
                <div class="text-center text-danger">
                    <h4>😭 遗憾离场</h4>
                    <p>得分: ${scoreDisplay}</p>
                    <p>距离分数线还差一点点...</p>
                </div>
            `;
            // 修改按钮行为为刷新
            document.querySelector('#resultModal .btn-primary').textContent = "重新考试";
            document.querySelector('#resultModal .btn-primary').onclick = () => location.reload();
            modalEl.show();
        }
        // 分配专业并展示抽签动画，动画结束后显示按钮供用户点击
        async function assignMajorWithAnimation(token) {
            const modalBody = document.getElementById('result-body');
            const modalEl = new bootstrap.Modal(document.getElementById('resultModal'), { backdrop: 'static' });
            const modalFooter = document.querySelector('#resultModal .modal-footer');
            try {
                const response = await fetch(`${API_BASE_URL}/api/assign_major`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token })
                });
                const data = await response.json();
                if (data.success) {
                    // 先隐藏底部按钮
                    if (modalFooter) modalFooter.style.display = 'none';
                    // 弹出模态框，展示抽签动画
                    modalEl.show();
                    await showLotteryAnimation(data.major);
                    // 动画结束后显示按钮
                    if (modalFooter) modalFooter.style.display = '';
                } else {
                    modalBody.innerHTML = `<div class="text-center text-danger">分配专业失败，请重试</div>`;
                    modalEl.show();
                }
            } catch (e) {
                modalBody.innerHTML = `<div class="text-center text-danger">网络异常，分配专业失败</div>`;
                modalEl.show();
            }
        }

        // 简单抽签动画实现
        function showLotteryAnimation(major) {
            return new Promise((resolve) => {
                const modalBody = document.getElementById('result-body');
                modalBody.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary mb-3" role="status" style="width: 4rem; height: 4rem;"></div>
                <h4>彩票系统发力中...</h4>
                <p class="mt-3">请稍候</p>
            </div>
        `;
                setTimeout(() => {
                    modalBody.innerHTML = `
                <div class="text-center text-success">
                    <h4>🎉 恭喜录取！</h4>
                    <p>你被分配到专业：<strong class="text-danger">${major}</strong></p>
                    <p class="text-muted mt-3">请点击下方按钮前往录取通知书</p>
                </div>
            `;
                    resolve();
                }, 1800);
            });
        }

    } catch (error) {
        console.error("提交考试失败:", error);
        document.getElementById('step-loading').style.display = 'none';

        const modalBody = document.getElementById('result-body');
        const modalEl = new bootstrap.Modal(document.getElementById('resultModal'), { backdrop: 'static' });

        modalBody.innerHTML = `
            <div class="text-center text-danger">
                <h4>❌ 网络异常</h4>
                <p class="text-muted">${error.message || '无法连接到服务器，请检查网络或稍后重试'}</p>
                <small class="text-muted">错误详情已输出到浏览器控制台</small>
            </div>
        `;
        document.querySelector('#resultModal .btn-primary').textContent = "刷新重试";
        document.querySelector('#resultModal .btn-primary').onclick = () => location.reload();
        modalEl.show();
    }
}

function goToGame() {
    window.location.href = '/admission';
}