<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits(['open'])
const tasks = ref([])
const newName = ref('')
const error = ref('')
const creating = ref(false)

async function load() {
  try {
    const data = await api.listTasks()
    tasks.value = data.items
  } catch (e) {
    error.value = e.message
  }
}

async function create() {
  if (!newName.value.trim()) return
  creating.value = true
  error.value = ''
  try {
    await api.createTask(newName.value.trim())
    newName.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}

const statusText = {
  created: '待上传',
  processing: '处理中',
  pending_review: '待审核',
  completed: '已完成',
  failed: '失败',
}
const statusTag = {
  created: 'info',
  processing: 'warn',
  pending_review: 'warn',
  completed: 'ok',
  failed: 'bad',
}

onMounted(load)
</script>

<template>
  <div class="card">
    <div class="row">
      <input v-model="newName" type="text" placeholder="新建比价任务名称，如：10月紧固件比价"
             @keyup.enter="create" style="flex:1; min-width:240px" />
      <button class="btn" :disabled="creating" @click="create">创建任务</button>
    </div>
    <p v-if="error" class="muted" style="color: var(--bad)">{{ error }}</p>
  </div>

  <div class="card">
    <h2 style="margin-top:0">比价任务</h2>
    <table>
      <thead>
        <tr><th>任务名称</th><th>状态</th><th>创建时间</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-if="!tasks.length"><td colspan="4" class="muted">还没有任务，先创建一个</td></tr>
        <tr v-for="t in tasks" :key="t.id">
          <td>{{ t.task_name }}</td>
          <td><span class="tag" :class="statusTag[t.status]">{{ statusText[t.status] || t.status }}</span></td>
          <td class="muted">{{ (t.created_at || '').replace('T', ' ').slice(0, 16) }}</td>
          <td><button class="btn ghost" @click="emit('open', t.id)">进入</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
