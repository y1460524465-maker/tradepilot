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

const steps = [
  { idx: '01', icon: '📤', title: '上传报价单', desc: '把各家供应商的 Excel / CSV / PDF 报价文件上传到同一个比价任务中。' },
  { idx: '02', icon: '🧠', title: '智能提取', desc: '系统自动识别表头、把杂乱报价统一成标准结构；疑难文件可开启 AI 辅助。' },
  { idx: '03', icon: '🔍', title: '人工审核', desc: '机器拿不准的条目会标记出来，由人工确认或驳回，确保数据可靠。' },
  { idx: '04', icon: '📊', title: '比价与导出', desc: '自动匹配同款产品、排出价格名次、标出最低价与异常涨幅，一键导出报告。' },
]

onMounted(load)
</script>

<template>
  <!-- 主视觉 -->
  <section class="hero reveal" style="--i: 0">
    <div class="shard-geo shard-1"></div>
    <div class="shard-geo shard-2"></div>
    <div class="shard-geo shard-3"></div>
    <div class="hero-inner">
      <span class="eyebrow">AI-POWERED COMPARISON ENGINE</span>
      <h1>把多份报价单<br /><span class="grad-text">一键比出最优价</span></h1>
      <p class="lede">
        TradePilot 帮你把<strong>各家供应商的报价文件</strong>统一提取、自动匹配同款产品、
        排出<strong>价格名次与涨幅</strong>。AI 只做辅助，所有价格计算由确定性代码完成，
        拿不准的条目一律交由人工审核。
      </p>
    </div>
  </section>

  <!-- 业务流程图解 -->
  <section class="card reveal" style="--i: 1">
    <div class="section-head">
      <div class="section-icon">🧭</div>
      <div>
        <h2>比价是怎么完成的？</h2>
        <p class="desc">四个步骤，从一堆格式各异的报价单，到一份可直接汇报的比价报告。</p>
      </div>
      <span class="no">WORKFLOW</span>
    </div>
    <div class="flow-grid">
      <div v-for="s in steps" :key="s.idx" class="flow-step">
        <div class="idx">{{ s.idx }}</div>
        <span class="icon">{{ s.icon }}</span>
        <h3>{{ s.title }}</h3>
        <p>{{ s.desc }}</p>
      </div>
    </div>
  </section>

  <!-- 新建任务 -->
  <section class="card reveal" style="--i: 2">
    <div class="section-head">
      <div class="section-icon">✨</div>
      <div>
        <h2>开始一次新比价</h2>
        <p class="desc">创建任务后，进入任务详情上传报价文件。</p>
      </div>
      <span class="no">00 / NEW</span>
    </div>
    <div class="row">
      <input v-model="newName" type="text" placeholder="任务名称，如：10 月紧固件比价"
             style="flex: 1; min-width: 260px" @keyup.enter="create" />
      <button class="btn" :disabled="creating" @click="create">＋ 创建比价任务</button>
    </div>
    <p v-if="error" class="muted" style="color: var(--bad-text); margin-bottom: 0">{{ error }}</p>
  </section>

  <!-- 任务列表 -->
  <section class="card reveal" style="--i: 3">
    <div class="section-head">
      <div class="section-icon">🗂️</div>
      <div>
        <h2>我的比价任务</h2>
        <p class="desc">点击卡片进入任务详情，继续未完成的流程。</p>
      </div>
      <span class="no">{{ tasks.length }} TASKS</span>
    </div>

    <div v-if="!tasks.length" class="empty">
      还没有任务 —— 上面输入名称，创建第一个比价任务 🚀
    </div>

    <div v-else class="task-grid">
      <div v-for="(t, i) in tasks" :key="t.id" class="task-card reveal"
           :style="{ '--i': i }" @click="emit('open', t.id)">
        <div class="row" style="justify-content: space-between">
          <span class="meta-mono">TASK · {{ String(t.id).padStart(3, '0') }}</span>
          <span class="tag" :class="statusTag[t.status]">{{ statusText[t.status] || t.status }}</span>
        </div>
        <div class="name" style="margin-top: 10px">{{ t.task_name }}</div>
        <div class="row" style="justify-content: space-between">
          <span class="meta-mono">{{ (t.created_at || '').replace('T', ' ').slice(0, 16) }}</span>
          <span class="meta-mono" style="color: var(--info-text)">打开 →</span>
        </div>
      </div>
    </div>
  </section>
</template>
