import { ref, onUnmounted } from 'vue'
import { useGameStore } from '../stores/gameStore'

export function useGameWebSocket() {
    const ws = ref(null)
    const isConnected = ref(false)
    const gameStore = useGameStore()
    
    let reconnectAttempts = 0
    const maxReconnectAttempts = 3
    const reconnectDelay = 3000
    let heartbeatInterval = null

    // 发送消息
    const send = (data) => {
        if (ws.value && ws.value.readyState === WebSocket.OPEN) {
            ws.value.send(JSON.stringify(data))
        }
    }

    // 心跳机制
    const startHeartbeat = () => {
        if (heartbeatInterval) clearInterval(heartbeatInterval)
        heartbeatInterval = setInterval(() => {
            send({ action: "ping" })
        }, 25000)
    }

    // 连接与事件路由
    const connect = (token = 'test_token', baseUrl = 'ws://localhost:8000') => {
        ws.value = new WebSocket(`${baseUrl}/ws/game`)

        ws.value.onopen = () => {
            // 💡 提示：后续我们会把 auth 模块也重构，这里先硬编码测试
            ws.value.send(JSON.stringify({ token: token }))
        }

        ws.value.onmessage = (event) => {
            const msg = JSON.parse(event.data)

            switch (msg.type) {
                case 'auth_ok':
                    isConnected.value = true
                    reconnectAttempts = 0
                    startHeartbeat()
                    gameStore.addLog('系统', '已连接服务器...', 'text-success')
                    // 认证成功后，如果服务器没有立刻发 init，可以保持在 loading 或请求状态
                    break;
                    
                case 'auth_error':
                    gameStore.addLog('系统', msg.message || '认证失败', 'text-danger')
                    break;

                case 'init':
                    // 收到 init 意味着开局完成或读取存档成功，正式进入游戏！
                    gameStore.setPhase('playing')
                    
                    gameStore.userInfo = msg.data
                    if (msg.data.course_info_json) {
                        gameStore.setCourseMetadata(JSON.parse(msg.data.course_info_json))
                    }
                    gameStore.updateStats(msg.data)
                    gameStore.semesterTimeLeft = msg.semester_time_left
                    break;

                case 'tick':
                    // 原本复杂的 updateGameView 现在只剩这几行状态赋值！
                    gameStore.updateStats(msg.stats)
                    if (msg.courses) gameStore.currentStats.courses = msg.courses
                    if (msg.course_states) gameStore.updateCourseStates(msg.course_states)
                    if (msg.semester_time_left !== undefined) {
                        gameStore.semesterTimeLeft = msg.semester_time_left
                    }
                    break;

                case 'paused':
                    gameStore.setPaused(true)
                    gameStore.addLog('系统', msg.msg || '游戏已暂停。', 'text-warning')
                    break;

                case 'resumed':
                    gameStore.setPaused(false)
                    gameStore.addLog('系统', msg.msg || '游戏已继续。', 'text-success')
                    break;

                case 'event':
                    gameStore.addLog('事件', msg.data.desc, 'text-primary')
                    break;

                case 'need_admission': 
                    // 假设你的后端在发现是新玩家时，会推送这个事件（具体按你的后端逻辑来）
                    gameStore.setPhase('admission')
                    gameStore.admissionData = msg.data // 把可供选择的专业/天赋数据存入 Store
                    break;

                // ---------------- 模态框/弹窗类事件 ----------------
                case 'game_over':
                    // 后端发送格式: type="game_over", data={"reason": "...", "restartable": True}
                    gameStore.triggerEndGame('game_over', { 
                        reason: msg.data.reason || '你在求是园中迷失了自我' 
                    })
                    break;

                case 'semester_summary':
                    gameStore.showModal('transcript', msg.data)
                    break;

                case 'random_event':
                    gameStore.showModal('random_event', msg.data)
                    break;
                    
                case 'dingtalk_message':
                    gameStore.addDingMessage(msg.data)
                    break;

                case 'graduation':
                    // 后端发送格式: type="graduation", data={"data": {"final_stats": {...}, "wenyan_report": "..."}}
                    // 注意这里的双层 msg.data.data 嵌套！
                    const gradData = msg.data.data || msg.data; 
                    const finalStats = gradData.final_stats || {};
                    
                    gameStore.triggerEndGame('graduation', {
                        gpa: parseFloat(finalStats.gpa || 0),
                        iq: finalStats.iq || 100,
                        eq: finalStats.eq || 100,
                        gold: finalStats.gold || 0,
                        achievements_count: (finalStats.achievements || []).length,
                        llm_summary: gradData.wenyan_report || '此子聪颖过人，勤勉有加...'
                    })
                    break;

                case 'new_semester':
                    // 原本的 alert 也可以改造成更友好的通知
                    gameStore.setCourseMetadata([])
                    gameStore.updateCourseStates({})
                    gameStore.clearEventLogs() // 清空日志
                    gameStore.addLog('系统', `=== 欢迎来到 ${msg.data.semester_name} ===`, 'text-success fw-bold')
                    break;

                // ✨ 新增：拦截保存结果并弹出 Toast
                case 'save_result':
                    gameStore.showToast(msg.message, msg.success ? 'success' : 'danger')
                    break;

                // ✨ 新增：拦截退出确认，直接切回登录或刷新页面
                case 'exit_confirmed':
                    // 清除 token 并直接刷新页面，回到最原始状态
                    localStorage.removeItem('zju_token')
                    window.location.reload()
                    break;
            }
        }

        ws.value.onclose = (event) => {
            isConnected.value = false
            if (heartbeatInterval) clearInterval(heartbeatInterval)
            
            if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
                reconnectAttempts++
                gameStore.addLog('系统', `断开连接，准备重连 (${reconnectAttempts}/${maxReconnectAttempts})...`, 'text-warning')
                setTimeout(() => connect(token, baseUrl), reconnectDelay)
            }
        }
    }

    // 组件卸载时自动清理
    onUnmounted(() => {
        if (ws.value) ws.value.close()
        if (heartbeatInterval) clearInterval(heartbeatInterval)
    })

    return {
        ws,
        isConnected,
        connect,
        send
    }
}