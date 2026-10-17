<script setup>
import { ref } from 'vue'
import TaskList from './components/TaskList.vue'
import TaskDetail from './components/TaskDetail.vue'

// 深链接支持：/?task=<id> 直达任务详情
const currentTaskId = ref(new URLSearchParams(location.search).get('task') || '')

function open(id) {
  currentTaskId.value = id
  history.replaceState(null, '', `/?task=${id}`)
  window.scrollTo({ top: 0 })
}

function back() {
  currentTaskId.value = ''
  history.replaceState(null, '', '/')
}
</script>

<template>
  <header class="topbar reveal" style="--i: 0">
    <div class="logo-badge">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M12 2L20.5 7.5V16.5L12 22L3.5 16.5V7.5L12 2Z" stroke="#4cc9f0" stroke-width="1.4" />
        <path d="M12 2V22M3.5 7.5L20.5 16.5M20.5 7.5L3.5 16.5" stroke="#8b7cff" stroke-width="0.7" opacity="0.7" />
      </svg>
    </div>
    <div class="wordmark">TradePilot<em>供应商比价工作台</em></div>
    <span class="meta-mono">QUOTATION · MATCH · COMPARE</span>
  </header>

  <TaskList v-if="!currentTaskId" @open="open" />
  <TaskDetail v-else :task-id="currentTaskId" @back="back" />

  <footer class="meta-mono">
    AI 只辅助，不决策 · 价格计算全部由确定性代码完成 · TradePilot MVP
  </footer>
</template>
