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

    const send = (data) => {
        if (ws.value && ws.value.readyState === WebSocket.OPEN) {
            ws.value.send(JSON.stringify(data))
        }
    }

    const startHeartbeat = () => {
        if (heartbeatInterval) clearInterval(heartbeatInterval)
        heartbeatInterval = setInterval(() => {
            send({ action: "ping" })
        }, 25000)
    }

    const connect = (token = 'test_token', baseUrl = 'ws://localhost:8000') => {
        ws.value = new WebSocket(`${baseUrl}/ws/game`)

        ws.value.onopen = () => {
            const llmModel = sessionStorage.getItem('custom_llm_model')
            const llmKey = sessionStorage.getItem('custom_llm_key')
            
            const payload = { token: token }
            if (llmModel && llmModel.trim() !== '') payload.custom_llm_model = llmModel.trim()
            if (llmKey && llmKey.trim() !== '') payload.custom_llm_api_key = llmKey.trim()
            
            ws.value.send(JSON.stringify(payload))
        }

        ws.value.onmessage = (event) => {
            const msg = JSON.parse(event.data)

            switch (msg.type) {
                case 'auth_ok':
                    isConnected.value = true
                    reconnectAttempts = 0
                    startHeartbeat()
                    gameStore.addLog('系统', '已连接服务器...', 'text-success')
                    
                    // 🌟 修复 3A：打出动作组合拳，确保无论是新开局还是断线重连，都能唤醒后端引擎！
                    send({ action: 'start' })
                    send({ action: 'resume' })
                    send({ action: 'get_state' })
                    break;
                    
                case 'auth_error':
                    gameStore.addLog('系统', msg.message || '认证失败', 'text-danger')
                    break;

                case 'init':
                    gameStore.setPhase('playing')
                    gameStore.userInfo = msg.data
                    if (msg.data.course_info_json) {
                        gameStore.setCourseMetadata(JSON.parse(msg.data.course_info_json))
                    }
                    gameStore.updateStats(msg.data)
                    gameStore.semesterTimeLeft = msg.semester_time_left
                    break;

                // 🌟 修复 3B：极端兜底逻辑。如果后端只发 tick 而遗漏了 init，强制打破 loading 卡死状态
                case 'tick':
                    if (gameStore.currentPhase !== 'playing') {
                        gameStore.setPhase('playing')
                    }
                    gameStore.updateStats(msg.stats)
                    if (msg.courses) gameStore.currentStats.courses = msg.courses
                    if (msg.course_states) gameStore.updateCourseStates(msg.course_states)
                    if (msg.semester_time_left !== undefined) {
                        gameStore.semesterTimeLeft = msg.semester_time_left
                    }
                    break;

                // 🌟 修复 3C：兼容部分后端返回 state 的情况
                case 'state':
                    if (gameStore.currentPhase !== 'playing') {
                        gameStore.setPhase('playing')
                    }
                    if (msg.data) gameStore.updateStats(msg.data)
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
                    // 🌟 修复：防止 msg.data 为 undefined 导致的报错
                    gameStore.addLog('事件', msg.data?.desc || msg.desc || '发生了未知事件', 'text-primary')
                    break;

                case 'game_over':
                    // 🌟 修复：安全读取 reason，兼容后端不同的打包格式
                    gameStore.triggerEndGame('game_over', { 
                        reason: msg.data?.reason || msg.reason || '你在求是园中迷失了自我' 
                    })
                    break;

                case 'semester_summary':
                    gameStore.showModal('transcript', msg.data || msg)
                    break;

                case 'random_event':
                    gameStore.showModal('random_event', msg.data || msg)
                    break;
                    
                case 'dingtalk_message':
                    gameStore.addDingMessage(msg.data || msg)
                    break;

                case 'graduation':
                    const gradData = msg.data?.data || msg.data || msg; 
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
                    gameStore.setCourseMetadata([])
                    gameStore.updateCourseStates({})
                    gameStore.eventLogs = [] 
                    gameStore.addLog('系统', `=== 欢迎来到 ${msg.data.semester_name} ===`, 'text-success fw-bold')
                    break;

                case 'save_result':
                    gameStore.showToast(msg.message, msg.success ? 'success' : 'danger')
                    if (gameStore.isPendingExit && msg.success) {
                        localStorage.removeItem('zju_token')
                        window.location.reload()
                    } else if (gameStore.isPendingExit && !msg.success) {
                         gameStore.isPendingExit = false
                         gameStore.addLog('系统', '保存失败，无法安全退出！', 'text-danger')
                    }
                    break;

                case 'exit_confirmed':
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

    onUnmounted(() => {
        if (ws.value) ws.value.close()
        if (heartbeatInterval) clearInterval(heartbeatInterval)
    })

    return { ws, isConnected, connect, send }
}