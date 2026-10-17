<script setup>
import { ref } from 'vue'
import TaskList from './components/TaskList.vue'
import TaskDetail from './components/TaskDetail.vue'

const currentTaskId = ref(null)
</script>

<template>
  <h1>TradePilot · 报价处理与供应商比价</h1>
  <TaskList v-if="!currentTaskId" @open="currentTaskId = $event" />
  <TaskDetail v-else :task-id="currentTaskId" @back="currentTaskId = null" />
</template>
