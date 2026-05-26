/** Engine API 调用层。 */

const BASE = '/api/traces'

export async function fetchTraces({ agentName, model, offset, limit } = {}) {
  const params = new URLSearchParams()
  if (agentName) params.set('agent_name', agentName)
  if (model) params.set('model', model)
  if (offset != null) params.set('offset', String(offset))
  if (limit != null) params.set('limit', String(limit || 50))

  const url = `${BASE}?${params.toString()}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchTrace(traceId) {
  const res = await fetch(`${BASE}/${traceId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchStats() {
  const res = await fetch(`${BASE}/stats/summary`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchDiagnosis(traceId) {
  const res = await fetch(`${BASE}/${traceId}/diagnose`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchCompare(traceIdA, traceIdB) {
  const res = await fetch(`${BASE}/compare?a=${traceIdA}&b=${traceIdB}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
