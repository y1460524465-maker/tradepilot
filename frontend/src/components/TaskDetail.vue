<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const props = defineProps({ taskId: String })
const emit = defineEmits(['back'])

const task = ref(null)
const files = ref([])
const items = ref([])
const review = ref(null)
const groups = ref([])
const error = ref('')
const busy = ref('')

const fileInput = ref(null)

const comparabilityText = { comparable: '可比', needs_review: '需人工确认', not_comparable: '不可比' }
const comparabilityTag = { comparable: 'ok', needs_review: 'warn', not_comparable: 'bad' }
const reviewTag = { pending_review: 'warn', confirmed: 'ok', rejected: 'bad' }
const reviewText = { pending_review: '待复核', confirmed: '已确认', rejected: '已驳回' }
const matchTypeText = { exact: '精确匹配', rule: '规则匹配', fuzzy: '待确认', single: '单家', manual: '人工' }

const comparableGroups = computed(
  () => groups.value.filter((g) => g.comparability === 'comparable').length
)

async function refresh() {
  task.value = await api.getTask(props.taskId)
  files.value = (await api.listFiles(props.taskId)).items
  items.value = (await api.listItems(props.taskId)).items
  review.value = await api.reviewSummary(props.taskId)
  groups.value = (await api.comparison(props.taskId)).groups
}

async function loadAll() {
  busy.value = '加载'
  error.value = ''
  try {
    await refresh()
  } catch (e) {
    error.value = `加载失败：${e.message}`
  } finally {
    busy.value = ''
  }
}

async function guard(fn, label) {
  busy.value = label
  error.value = ''
  try {
    await fn()
    await refresh()
  } catch (e) {
    error.value = `${label}失败：${e.message}`
  } finally {
    busy.value = ''
  }
}

async function upload() {
  const files = fileInput.value?.files
  if (!files || !files.length) { error.value = '请先选择文件'; return }
  await guard(async () => { await api.uploadFiles(props.taskId, files) }, '上传')
  if (fileInput.value) fileInput.value.value = ''
}

function rankSorted(group) {
  return [...group.items].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
}

onMounted(loadAll)
</script>

<template>
  <!-- 任务刊头 -->
  <div v-if="task" class="reveal" style="--i: 0; margin-top: 32px">
    <button class="btn ghost" @click="emit('back')">← 返回任务列表</button>
    <div class="row" style="margin-top: 18px; gap: 14px">
      <h1 style="font-size: 26px">{{ task.task_name }}</h1>
      <span class="tag info">{{ task.status }}</span>
    </div>
    <p class="meta-mono" style="margin: 6px 0 0">
      TASK {{ props.taskId.slice(0, 8).toUpperCase() }}
    </p>
  </div>

  <!-- bento 统计 -->
  <div v-if="review" class="stats reveal" style="--i: 1">
    <div class="stat">
      <div class="label">报价明细</div>
      <div class="value">{{ review.total_items }}</div>
    </div>
    <div class="stat" :class="{ warn: review.pending_review > 0 }">
      <div class="label">待复核</div>
      <div class="value">{{ review.pending_review }}</div>
    </div>
    <div class="stat" :class="{ ok: review.by_status.confirmed > 0 }">
      <div class="label">已确认</div>
      <div class="value">{{ review.by_status.confirmed }}</div>
    </div>
    <div class="stat">
      <div class="label">可比组</div>
      <div class="value">{{ comparableGroups }}</div>
    </div>
  </div>

  <p v-if="busy" class="meta-mono reveal" style="--i: 1; margin-top: 16px">正在{{ busy }}…</p>
  <p v-if="error" class="reveal" style="--i: 1; color: var(--red-text); font-size: 13px">{{ error }}</p>

  <!-- 01 上传 -->
  <section v-if="task" class="card reveal" style="--i: 2">
    <div class="section-head">
      <span class="no">01 / UPLOAD</span>
      <h2>上传报价文件</h2>
    </div>
    <div class="row">
      <input ref="fileInput" type="file" multiple accept=".xlsx,.csv,.pdf" />
      <button class="btn" :disabled="!!busy" @click="upload">上传</button>
      <button class="btn ghost" :disabled="!!busy" @click="guard(() => api.extract(taskId), '解析提取')">解析提取</button>
      <button class="btn ghost" :disabled="!!busy" @click="guard(() => api.aiExtract(taskId), 'AI 提取')">AI 辅助提取</button>
    </div>
    <p class="muted" style="margin-bottom: 0">支持 xlsx / csv / pdf，单文件 20MB；解析失败会逐文件标记原因。</p>

    <table v-if="files.length" style="margin-top: 18px">
      <thead><tr><th>文件名</th><th>类型</th><th>大小</th><th>状态</th><th></th></tr></thead>
      <tbody>
        <tr v-for="f in files" :key="f.id">
          <td style="color: var(--ink)">{{ f.original_filename }}</td>
          <td class="meta-mono">{{ f.file_type }}</td>
          <td class="meta-mono">{{ (f.file_size / 1024).toFixed(1) }} KB</td>
          <td>
            <span class="tag" :class="f.status === 'parsed' ? 'ok' : f.status === 'parse_failed' ? 'bad' : 'info'">
              {{ f.status === 'parsed' ? '已解析' : f.status === 'parse_failed' ? '解析失败' : f.status }}
            </span>
            <span v-if="f.error_message" class="muted"> {{ f.error_message }}</span>
          </td>
          <td style="text-align: right"><a :href="api.downloadFile(taskId, f.id)">下载原件</a></td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- 02 审核 -->
  <section v-if="review" class="card reveal" style="--i: 3">
    <div class="section-head">
      <span class="no">02 / REVIEW</span>
      <h2>人工审核</h2>
    </div>
    <div class="row">
      <span class="tag warn" v-if="review.pending_review">待复核 {{ review.pending_review }}</span>
      <span class="tag ok" v-if="review.by_status.confirmed">已确认 {{ review.by_status.confirmed }}</span>
      <button class="btn" style="margin-left: auto" :disabled="!review.pending_review || !!busy"
              @click="guard(() => api.confirmReview(taskId, { all: true }), '批量确认')">
        全部确认
      </button>
    </div>
    <div v-if="review.issues.length" class="issue-list">
      <div v-for="(it, i) in review.issues.slice(0, 5)" :key="i">{{ it.issue }}</div>
      <div v-if="review.issues.length > 5">…共 {{ review.issues.length }} 条问题</div>
    </div>
  </section>

  <!-- 03 匹配比价 -->
  <section class="card reveal" style="--i: 4">
    <div class="section-head">
      <span class="no">03 / COMPARE</span>
      <h2>匹配与比价</h2>
    </div>
    <div class="row" style="margin-bottom: 8px">
      <button class="btn" :disabled="!!busy" @click="guard(() => api.match(taskId), '匹配比价')">执行匹配比价</button>
      <a class="btn ghost" :href="api.exportUrl(taskId)">导出比价报告 xlsx</a>
    </div>

    <div v-if="!groups.length" class="empty">还没有匹配结果 —— 点击「执行匹配比价」</div>

    <div v-for="(g, gi) in groups" :key="g.match_id" :style="gi > 0 ? 'margin-top: 28px' : ''">
      <div class="row" style="margin-bottom: 6px">
        <strong style="color: var(--ink); font-size: 14.5px">
          {{ g.product_name }} <span v-if="g.model" class="meta-mono">{{ g.model }}</span>
        </strong>
        <span class="tag" :class="comparabilityTag[g.comparability]">{{ comparabilityText[g.comparability] }}</span>
        <span class="tag info">{{ matchTypeText[g.match_type] }}</span>
      </div>
      <p v-if="g.reasons.length" class="muted" style="margin: 2px 0 8px">注：{{ g.reasons.join('；') }}</p>
      <table>
        <thead>
          <tr><th>#</th><th>供应商</th><th>单价</th><th>币种</th><th>数量</th><th>估算总价</th><th>差额</th><th>涨幅</th><th>问题</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in rankSorted(g)" :key="c.item_id" :class="{ best: c.item_id === g.best_item_id }">
            <td class="meta-mono">{{ c.rank ?? '—' }}</td>
            <td style="color: var(--ink)">{{ c.supplier_name || '—' }}</td>
            <td class="num">{{ c.unit_price ?? '—' }}</td>
            <td class="meta-mono">{{ c.currency ?? '—' }}</td>
            <td class="num">{{ c.quantity ?? '—' }}</td>
            <td class="num">{{ c.estimated_total ?? '—' }}</td>
            <td class="num">{{ c.diff_abs ?? '—' }}</td>
            <td class="num" :class="{ 'diff-warn': c.diff_pct !== null && c.diff_pct > 10 }">
              {{ c.diff_pct !== null ? c.diff_pct + '%' : '—' }}
            </td>
            <td class="muted">{{ c.issues.join('；') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- 04 明细 -->
  <section class="card reveal" style="--i: 5">
    <div class="section-head">
      <span class="no">04 / ITEMS</span>
      <h2>报价明细</h2>
      <span class="meta-mono" style="margin-left: auto">{{ items.length }} 条</span>
    </div>
    <div v-if="!items.length" class="empty">暂无明细 —— 先上传并解析报价文件</div>
    <table v-else>
      <thead><tr><th>供应商</th><th>产品</th><th>型号</th><th>规格</th><th>数量</th><th>单价</th><th>币种</th><th>审核</th><th>来源</th></tr></thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td style="color: var(--ink)">{{ it.supplier_name || '—' }}</td>
          <td>{{ it.product_name || '—' }}</td>
          <td class="meta-mono">{{ it.model || '—' }}</td>
          <td class="meta-mono">{{ it.specification || '—' }}</td>
          <td class="num">{{ it.quantity ?? '—' }}</td>
          <td class="num">{{ it.unit_price ?? '—' }}</td>
          <td class="meta-mono">{{ it.currency ?? '—' }}</td>
          <td><span class="tag" :class="reviewTag[it.review_status]">{{ reviewText[it.review_status] }}</span></td>
          <td class="meta-mono">
            {{ (it.source_reference?.file || '') + (it.source_reference?.row ? ` 第${it.source_reference.row}行` : '') }}
            <span v-if="it.extraction_method === 'ai'" class="tag warn">AI</span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
