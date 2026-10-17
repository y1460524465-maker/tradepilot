const BASE = '/api/v1'

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, options)
  if (!resp.ok) {
    let detail = `${resp.status}`
    try {
      const body = await resp.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return resp.json()
}

export const api = {
  // 任务
  listTasks: () => request('/tasks'),
  createTask: (task_name) =>
    request('/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_name }),
    }),
  getTask: (id) => request(`/tasks/${id}`),

  // 文件
  listFiles: (id) => request(`/tasks/${id}/files`),
  uploadFiles: (id, files) => {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    return request(`/tasks/${id}/files`, { method: 'POST', body: form })
  },
  downloadFile: (taskId, fileId) => `${BASE}/tasks/${taskId}/files/${fileId}/download`,

  // 提取 / 匹配 / AI
  extract: (id) => request(`/tasks/${id}/extract`, { method: 'POST' }),
  aiExtract: (id) => request(`/tasks/${id}/ai_extract`, { method: 'POST' }),
  match: (id) => request(`/tasks/${id}/match`, { method: 'POST' }),

  // 报价明细与审核
  listItems: (id) => request(`/tasks/${id}/items?limit=500`),
  reviewSummary: (id) => request(`/tasks/${id}/review`),
  confirmReview: (id, payload) =>
    request(`/tasks/${id}/review/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // 比价与导出
  comparison: (id) => request(`/tasks/${id}/matches`),
  exportUrl: (id) => `${BASE}/tasks/${id}/export`,
}
