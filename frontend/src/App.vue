<script setup>
import { ref } from 'vue'
import TaskList from './components/TaskList.vue'
import TaskDetail from './components/TaskDetail.vue'

// 深链接支持：/?task=<id> 直达任务详情
const currentTaskId = ref(new URLSearchParams(location.search).get('task') || '')

function open(id) {
  currentTaskId.value = id
  history.replaceState(null, '', `/?task=${id}`)
}

function back() {
  currentTaskId.value = ''
  history.replaceState(null, '', '/')
}
</script>

<template>
  <header class="masthead">
    <div class="wordmark reveal" style="--i: 0">
      TradePilot<em> · 供应商比价工作台</em>
    </div>
    <span class="meta-mono reveal" style="--i: 1">QUOTATION · MATCH · COMPARE</span>
  </header>

  <TaskList v-if="!currentTaskId" @open="open" />
  <TaskDetail v-else :task-id="currentTaskId" @back="back" />

  <footer class="meta-mono" style="margin-top: 48px; text-align: center">
    AI 只辅助，不决策 · 价格计算全部由确定性代码完成
  </footer>
</template>
