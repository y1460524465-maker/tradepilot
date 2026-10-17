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
  <!-- 新建任务 -->
  <section class="card reveal" style="--i: 1">
    <div class="section-head">
      <span class="no">00 / NEW</span>
      <h2>新建比价任务</h2>
    </div>
    <div class="row">
      <input v-model="newName" type="text" placeholder="任务名称，如：10 月紧固件比价"
             style="flex: 1; min-width: 240px" @keyup.enter="create" />
      <button class="btn" :disabled="creating" @click="create">创建任务</button>
    </div>
    <p v-if="error" class="muted" style="color: var(--red-text); margin-bottom: 0">{{ error }}</p>
  </section>

  <!-- 任务列表 -->
  <section class="card reveal" style="--i: 2">
    <div class="section-head">
      <span class="no">01 / TASKS</span>
      <h2>比价任务</h2>
      <span class="meta-mono" style="margin-left: auto">{{ tasks.length }} 项</span>
    </div>

    <div v-if="!tasks.length" class="empty">
      还没有任务 —— 输入名称，创建第一个比价任务
    </div>

    <table v-else>
      <thead>
        <tr><th>任务名称</th><th>状态</th><th>创建时间</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="(t, i) in tasks" :key="t.id" class="reveal" :style="{ '--i': i }">
          <td style="color: var(--ink)">{{ t.task_name }}</td>
          <td><span class="tag" :class="statusTag[t.status]">{{ statusText[t.status] || t.status }}</span></td>
          <td class="meta-mono">{{ (t.created_at || '').replace('T', ' ').slice(0, 16) }}</td>
          <td style="text-align: right">
            <button class="btn ghost" @click="emit('open', t.id)">打开</button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
