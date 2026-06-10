<template>
  <div ref="container" class="mermaid-host">
    <pre v-if="renderError" class="mermaid-fallback">{{ decodedCode }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  code: string
}>()

const container = ref<HTMLDivElement | null>(null)
const renderError = ref(false)
const decodedCode = computed(() => decodeURIComponent(props.code))

async function renderMermaid() {
  if (!container.value) return
  renderError.value = false
  try {
    const mermaid = (await import('mermaid')).default
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: document.documentElement.classList.contains('dark') ? 'dark' : 'default',
    })
    const id = `mermaid-${Math.random().toString(36).slice(2)}`
    const { svg } = await mermaid.render(id, decodedCode.value)
    container.value.innerHTML = svg
  } catch {
    renderError.value = true
  }
}

onMounted(renderMermaid)
watch(() => props.code, renderMermaid)
</script>
