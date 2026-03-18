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
            const llmProvider = sessionStorage.getItem('custom_llm_provider')
            const llmModel = sessionStorage.getItem('custom_llm_model')
            const llmKey = sessionStorage.getItem('custom_llm_key')
            
            const payload = { token: token }
            if (llmProvider) payload.custom_llm_provider = llmProvider
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
                    // 1. 设置静态元数据
                    if (msg.data.course_info_json) {
                        gameStore.setCourseMetadata(JSON.parse(msg.data.course_info_json))
                    }
                    // 2. 更新基础属性
                    gameStore.updateStats(msg.data)
                    // 3. 如果 init 阶段也带了实时课程状态，更新它
                    if (msg.data.courses) {
                         gameStore.updateCourseStates(msg.data.courses)
                    }
                    gameStore.semesterTimeLeft = msg.semester_time_left
                    break;

                case 'tick':
                    if (gameStore.currentPhase !== 'playing') {
                        gameStore.setPhase('playing')
                    }
                    // 1. 更新基础属性 (iq, eq, energy, sanity)
                    gameStore.updateStats(msg.stats)
                    // 2. 🌟 修复：专门更新课程实时状态
                    if (msg.courses) gameStore.updateCourseStates(msg.courses)
                    if (msg.course_states) gameStore.updateCourseStates(msg.course_states)
                    
                    if (msg.semester_time_left !== undefined) {
                        gameStore.semesterTimeLeft = msg.semester_time_left
                    }
                    break;

                case 'state':
                    if (gameStore.currentPhase !== 'playing') {
                        gameStore.setPhase('playing')
                    }
                    if (msg.data) {
                        gameStore.updateStats(msg.data)
                        if (msg.data.courses) gameStore.updateCourseStates(msg.data.courses)
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
                    gameStore.addLog('事件', msg.data?.desc || msg.desc || '发生了未知事件', 'text-primary')
                    break;

                case 'game_over':
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

                case 'graduation': {
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
                }

                case 'new_semester':
                    gameStore.setCourseMetadata([])
                    gameStore.updateCourseStates({})
                    gameStore.eventLogs = [] 
                    gameStore.addLog('系统', `=== 欢迎来到 ${msg.data?.semester_name || msg.semester_name || '新学期'} ===`, 'text-success fw-bold')
                    break;

                case 'save_result':
                    gameStore.showToast && gameStore.showToast(msg.message, msg.success ? 'success' : 'danger')
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