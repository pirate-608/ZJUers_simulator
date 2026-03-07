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
            // 🌟 修复：从 sessionStorage 提取自定义大模型配置，伴随 Token 一起发给后端引擎
            const llmModel = sessionStorage.getItem('custom_llm_model')
            const llmKey = sessionStorage.getItem('custom_llm_key')
            
            ws.value.send(JSON.stringify({ 
                token: token,
                custom_llm_model: llmModel || null,
                custom_llm_api_key: llmKey || null
            }))
        }

        ws.value.onmessage = (event) => {
            const msg = JSON.parse(event.data)

            switch (msg.type) {
                case 'auth_ok':
                    isConnected.value = true
                    reconnectAttempts = 0
                    startHeartbeat()
                    gameStore.addLog('系统', '已连接服务器...', 'text-success')
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

                case 'tick':
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

                case 'game_over':
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
                    gameStore.setCourseMetadata([])
                    gameStore.updateCourseStates({})
                    gameStore.eventLogs = [] 
                    gameStore.addLog('系统', `=== 欢迎来到 ${msg.data.semester_name} ===`, 'text-success fw-bold')
                    break;

                case 'save_result':
                    gameStore.showToast(msg.message, msg.success ? 'success' : 'danger')
                    
                    // 🌟 修复：如果当前处于“保存并退出”的等待状态，且保存成功，则执行退出流程
                    if (gameStore.isPendingExit && msg.success) {
                        localStorage.removeItem('zju_token')
                        window.location.reload()
                    } else if (gameStore.isPendingExit && !msg.success) {
                         // 如果保存失败，解除等待状态，让玩家重试
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