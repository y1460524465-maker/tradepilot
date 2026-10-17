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

async function guard(fn, label) {
  busy.value = label
  error.value = ''
  try {
    await fn()
    await loadAll()
  } catch (e) {
    error.value = `${label}失败：${e.message}`
  } finally {
    busy.value = ''
  }
}

const loadAll = () =>
  guard(async () => {
    task.value = await api.getTask(props.taskId)
    files.value = (await api.listFiles(props.taskId)).items
    items.value = (await api.listItems(props.taskId)).items
    review.value = await api.reviewSummary(props.taskId)
    groups.value = (await api.comparison(props.taskId)).groups
  }, '加载')

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
  <button class="btn ghost" @click="emit('back')">← 返回任务列表</button>

  <div v-if="task" class="card" style="margin-top:12px">
    <div class="row">
      <h2 style="margin:0">{{ task.task_name }}</h2>
      <span class="tag info">{{ task.status }}</span>
    </div>

    <h2>1 · 上传报价文件</h2>
    <div class="row">
      <input ref="fileInput" type="file" multiple accept=".xlsx,.csv,.pdf" />
      <button class="btn" :disabled="!!busy" @click="upload">上传</button>
      <button class="btn ghost" :disabled="!!busy" @click="guard(() => api.extract(taskId), '解析提取')">解析提取</button>
      <button class="btn ghost" :disabled="!!busy" @click="guard(() => api.aiExtract(taskId), 'AI 提取')">AI 辅助提取</button>
    </div>
    <p class="muted">支持 xlsx / csv / pdf，单文件 20MB；解析失败会逐文件标记原因。</p>

    <table v-if="files.length">
      <thead><tr><th>文件名</th><th>类型</th><th>大小</th><th>状态</th><th></th></tr></thead>
      <tbody>
        <tr v-for="f in files" :key="f.id">
          <td>{{ f.original_filename }}</td>
          <td>{{ f.file_type }}</td>
          <td class="muted">{{ (f.file_size / 1024).toFixed(1) }} KB</td>
          <td>
            <span class="tag" :class="f.status === 'parsed' ? 'ok' : f.status === 'parse_failed' ? 'bad' : 'info'">
              {{ f.status === 'parsed' ? '已解析' : f.status === 'parse_failed' ? '解析失败' : f.status }}
            </span>
            <span v-if="f.error_message" class="muted"> {{ f.error_message }}</span>
          </td>
          <td><a :href="api.downloadFile(taskId, f.id)">下载原件</a></td>
        </tr>
      </tbody>
    </table>
  </div>

  <div v-if="review" class="card">
    <h2 style="margin-top:0">2 · 人工审核</h2>
    <div class="row">
      <span>明细 {{ review.total_items }} 条</span>
      <span class="tag warn" v-if="review.pending_review">待复核 {{ review.pending_review }}</span>
      <span class="tag ok" v-if="review.by_status.confirmed">已确认 {{ review.by_status.confirmed }}</span>
      <button class="btn" :disabled="!review.pending_review || !!busy"
              @click="guard(() => api.confirmReview(taskId, { all: true }), '批量确认')">
        全部确认
      </button>
    </div>
    <ul v-if="review.issues.length" class="muted" style="margin-bottom:0">
      <li v-for="(it, i) in review.issues.slice(0, 5)" :key="i">{{ it.issue }}</li>
      <li v-if="review.issues.length > 5">…共 {{ review.issues.length }} 条问题</li>
    </ul>
  </div>

  <div class="card">
    <h2 style="margin-top:0">3 · 匹配与比价</h2>
    <div class="row" style="margin-bottom:10px">
      <button class="btn" :disabled="!!busy" @click="guard(() => api.match(taskId), '匹配比价')">执行匹配比价</button>
      <a class="btn ghost" :href="api.exportUrl(taskId)">导出比价报告 xlsx</a>
    </div>

    <div v-for="g in groups" :key="g.match_id" style="margin-bottom:18px">
      <div class="row">
        <strong>{{ g.product_name }} <span v-if="g.model" class="muted">{{ g.model }}</span></strong>
        <span class="tag" :class="comparabilityTag[g.comparability]">{{ comparabilityText[g.comparability] }}</span>
        <span class="tag info">{{ { exact: '精确匹配', rule: '规则匹配', fuzzy: '待确认', single: '单家', manual: '人工' }[g.match_type] }}</span>
      </div>
      <p v-if="g.reasons.length" class="muted" style="margin:4px 0">⚠ {{ g.reasons.join('；') }}</p>
      <table>
        <thead><tr><th>#</th><th>供应商</th><th>单价</th><th>币种</th><th>数量</th><th>估算总价</th><th>差额</th><th>涨幅</th><th>问题</th></tr></thead>
        <tbody>
          <tr v-for="c in rankSorted(g)" :key="c.item_id" :class="{ best: c.item_id === g.best_item_id }">
            <td>{{ c.rank ?? '—' }}</td>
            <td>{{ c.supplier_name || '—' }}</td>
            <td>{{ c.unit_price ?? '—' }}</td>
            <td>{{ c.currency ?? '—' }}</td>
            <td>{{ c.quantity ?? '—' }}</td>
            <td>{{ c.estimated_total ?? '—' }}</td>
            <td>{{ c.diff_abs ?? '—' }}</td>
            <td :class="{ 'diff-warn': c.diff_pct !== null && c.diff_pct > 10 }">
              {{ c.diff_pct !== null ? c.diff_pct + '%' : '—' }}
            </td>
            <td class="muted">{{ c.issues.join('；') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!groups.length" class="muted">还没有匹配结果，点击「执行匹配比价」。</p>
  </div>

  <div class="card">
    <h2 style="margin-top:0">4 · 报价明细（{{ items.length }} 条）</h2>
    <table>
      <thead><tr><th>供应商</th><th>产品</th><th>型号</th><th>规格</th><th>数量</th><th>单价</th><th>币种</th><th>审核</th><th>来源</th></tr></thead>
      <tbody>
        <tr v-if="!items.length"><td colspan="9" class="muted">暂无明细，先上传并解析文件</td></tr>
        <tr v-for="it in items" :key="it.id">
          <td>{{ it.supplier_name || '—' }}</td>
          <td>{{ it.product_name || '—' }}</td>
          <td>{{ it.model || '—' }}</td>
          <td>{{ it.specification || '—' }}</td>
          <td>{{ it.quantity ?? '—' }}</td>
          <td>{{ it.unit_price ?? '—' }}</td>
          <td>{{ it.currency ?? '—' }}</td>
          <td><span class="tag" :class="reviewTag[it.review_status]">{{ reviewText[it.review_status] }}</span></td>
          <td class="muted">
            {{ (it.source_reference?.file || '') + (it.source_reference?.row ? ` 第${it.source_reference.row}行` : '') }}
            <span v-if="it.extraction_method === 'ai'" class="tag warn">AI</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <p v-if="error" style="color: var(--bad)">{{ error }}</p>
  <p v-if="busy" class="muted">正在{{ busy }}…</p>
</template>
