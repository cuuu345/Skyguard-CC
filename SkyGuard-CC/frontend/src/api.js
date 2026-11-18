async function request(path, options) {
  const response = await fetch(path, options)
  const body = await response.json().catch(() => null)

  if (!response.ok) {
    const detail = body?.detail
    throw new Error(
      typeof detail === 'string' ? detail : `Request failed (${response.status})`,
    )
  }

  return body
}

export function getHealth() {
  return request('/api/health')
}

export function getDatabaseHealth() {
  return request('/api/db/health')
}

export function getModels() {
  return request('/api/models')
}

export function uploadModel(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request('/api/models', { method: 'POST', body: formData })
}

export function uploadDetection(
  file,
  { confidence = 0.25, nmsIou = 0.45, modelId = '' } = {},
) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('confidence', String(confidence))
  formData.append('nms_iou', String(nmsIou))
  formData.append('model_id', modelId)

  return request('/api/detections', {
    method: 'POST',
    body: formData,
  })
}

export function getDetectionHistory({ limit = 50, offset = 0 } = {}) {
  const query = new URLSearchParams({ limit, offset })
  return request(`/api/detections?${query}`)
}

export function queryDetectionHistory({
  q = '',
  status = '',
  dateFrom = '',
  dateTo = '',
  limit = 20,
  offset = 0,
} = {}) {
  const query = new URLSearchParams({ q, limit, offset })
  if (status) query.set('status', status)
  if (dateFrom) query.set('date_from', dateFrom)
  if (dateTo) query.set('date_to', dateTo)
  return request(`/api/detections/query?${query}`)
}

export function getAnalyticsSummary() {
  return request('/api/analytics/summary')
}

export function getDetection(taskId) {
  return request(`/api/detections/${taskId}`)
}

export function getImageContentUrl(imageId) {
  return `/api/detections/images/${imageId}/content`
}

export function getAnnotatedImageUrl(taskId) {
  return `/api/detections/${taskId}/annotated`
}

export function getAnnotatedImageStatus(taskId) {
  return request(`/api/detections/${taskId}/annotated/status`)
}
