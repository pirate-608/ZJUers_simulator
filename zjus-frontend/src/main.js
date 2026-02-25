import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css' // 如果你有全局样式的话
import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.mount('#app')