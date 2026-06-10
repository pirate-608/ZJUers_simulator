import DefaultTheme from 'vitepress/theme'
import { createPinia } from 'pinia'
import type { Theme } from 'vitepress'
import HomePage from './components/HomePage.vue'
import InteractiveGameDemo from './components/InteractiveGameDemo.vue'
import MermaidDiagram from './components/MermaidDiagram.vue'
import './styles.css'
import './bootstrap-lite.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.use(createPinia())
    app.component('HomePage', HomePage)
    app.component('InteractiveGameDemo', InteractiveGameDemo)
    app.component('MermaidDiagram', MermaidDiagram)
  },
} satisfies Theme
