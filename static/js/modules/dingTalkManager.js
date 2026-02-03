// ==========================================
// 钉钉消息管理模块
// ==========================================

export class DingTalkManager {
    renderDingtalkMessage(msg) {
        const container = document.getElementById('ding-messages');
        if (!container) return;

        if (container.querySelector('.text-center.text-muted')) {
            container.innerHTML = '';
        }

        const roleConfig = {
            "counselor": { bg: "#FF9F43", icon: "导", name: "辅导员" },
            "teacher": { bg: "#54a0ff", icon: "师", name: "老师" },
            "student": { bg: "#1dd1a1", icon: "生", name: "同学" },
            "system": { bg: "#8395a7", icon: "系", name: "系统通知" }
        };

        const config = roleConfig[msg.role] || roleConfig["student"];
        const senderName = msg.sender || config.name;
        const isUrgent = msg.is_urgent;

        const msgDiv = document.createElement('div');
        msgDiv.className = "d-flex align-items-start mb-3 ding-msg-anim";

        const bubbleStyle = isUrgent ? "border: 1px solid #ff6b6b; background: #fff0f0;" : "background: white; border: 1px solid #eee;";
        const urgentBadge = isUrgent ? `<span class="badge bg-danger ms-2" style="font-size:0.6rem">紧急</span>` : "";

        msgDiv.innerHTML = `
            <div class="flex-shrink-0">
                <div class="rounded-circle d-flex align-items-center justify-content-center text-white fw-bold shadow-sm" 
                     style="width: 36px; height: 36px; background-color: ${config.bg}; font-size: 0.85rem;">
                    ${config.icon}
                </div>
            </div>
            <div class="flex-grow-1 ms-2">
                <div class="d-flex align-items-center mb-1">
                    <span class="fw-bold text-dark" style="font-size: 0.85rem;">${senderName}</span>
                    <span class="text-muted ms-2" style="font-size: 0.7rem;">刚刚</span>
                    ${urgentBadge}
                </div>
                <div class="p-2 rounded shadow-sm position-relative" style="${bubbleStyle} border-radius: 0 8px 8px 8px;">
                    <p class="mb-0 text-dark" style="font-size: 0.9rem; line-height: 1.4;">
                        ${msg.content}
                    </p>
                </div>
            </div>
        `;

        container.appendChild(msgDiv);

        const cardBody = container.parentElement;
        cardBody.scrollTo({ top: cardBody.scrollHeight, behavior: 'smooth' });

        const badge = document.getElementById('ding-unread');
        if (badge) {
            let count = parseInt(badge.innerText) || 0;
            badge.innerText = count + 1;
            badge.style.display = 'inline-block';

            badge.classList.add('pulse-animation');
            setTimeout(() => badge.classList.remove('pulse-animation'), 1000);
        }
    }
}

export const dingTalkManager = new DingTalkManager();
