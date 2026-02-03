// ==========================================
// WebSocket 连接管理模块
// ==========================================

import { logEvent } from './utils.js';

export class WebSocketManager {
    constructor(messageHandler) {
        this.ws = null;
        this.messageHandler = messageHandler;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.reconnectDelay = 3000;
        this.heartbeatInterval = null;
    }

    connect() {
        const token = typeof auth !== 'undefined' ? auth.getToken() : 'test_token';
        const baseUrl = typeof WS_BASE_URL !== 'undefined' ? WS_BASE_URL : 'ws://localhost:8000';

        try {
            this.ws = new WebSocket(`${baseUrl}/ws/game?token=${token}`);

            this.ws.onopen = () => {
                logEvent("系统", "已连接zdbk...", "text-success");
                this.reconnectAttempts = 0;
                this.startHeartbeat();
            };

            this.ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                this.messageHandler(msg);
            };

            this.ws.onclose = (event) => {
                console.log('[WebSocket] Connection closed', event);
                this.stopHeartbeat();

                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    logEvent("系统", `连接已断开，${this.reconnectDelay / 1000}秒后尝试重连（${this.reconnectAttempts}/${this.maxReconnectAttempts}）...`, "text-warning");

                    setTimeout(() => {
                        logEvent("系统", "正在重新连接...", "text-info");
                        this.connect();
                    }, this.reconnectDelay);
                } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                    logEvent("系统", "连接失败次数过多，请刷新页面重试。", "text-danger");
                }
            };

            this.ws.onerror = (err) => {
                console.error("[WebSocket] Error", err);
                logEvent("系统", "连接出现错误", "text-danger");
            };
        } catch (error) {
            console.error('[WebSocket] Failed to create WebSocket', error);
            logEvent("系统", "无法建立连接，请检查网络", "text-danger");
        }
    }

    startHeartbeat() {
        this.stopHeartbeat();

        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                try {
                    this.send({ action: "ping" });
                } catch (e) {
                    console.error('[WebSocket] Heartbeat failed', e);
                }
            }
        }, 25000);
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    getWebSocket() {
        return this.ws;
    }

    close() {
        this.stopHeartbeat();
        if (this.ws) {
            this.ws.close();
        }
    }
}
