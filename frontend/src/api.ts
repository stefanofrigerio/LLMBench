import type { BenchmarkResult, ScoreEntry, Recommendation, ProvisionConfig, ProvisionState, Worker, QueueStatus, LocalRunResponse } from './types'

const BASE = ''

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function fetchWorkers(): Promise<{ workers: Worker[] }> {
  return apiFetch('/api/workers')
}

export async function fetchStatus(): Promise<{
  queue_status: QueueStatus
  worker_stats: Record<string, number>
  active_workers: number
  run_id: string | null
}> {
  return apiFetch('/api/status')
}

export async function fetchResults(
  capability?: string,
  modelName?: string,
): Promise<{ results: BenchmarkResult[]; count: number }> {
  const params = new URLSearchParams()
  if (capability) params.set('capability', capability)
  if (modelName) params.set('model_name', modelName)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return apiFetch(`/api/results${qs}`)
}

export async function fetchScores(
  capability: string,
  complexity: number,
): Promise<{ capability: string; complexity: number; models: ScoreEntry[] }> {
  const params = new URLSearchParams({ capability, complexity: String(complexity) })
  return apiFetch(`/api/scores?${params.toString()}`)
}

export async function recommend(
  capability: string,
  complexity: number,
  sensitivity: number,
): Promise<{ recommendation: Recommendation | null; message?: string }> {
  return apiFetch('/api/recommend', {
    method: 'POST',
    body: JSON.stringify({ capability, complexity, sensitivity }),
  })
}

export async function dispatch(req: {
  run_id: string
  models: Array<{ name: string; provider: string; model_id: string }>
  capabilities: string[]
  complexity_range: [number, number]
}): Promise<{ status: string; run_id: string; total_tasks: number; active_workers: number }> {
  return apiFetch('/api/dispatch', { method: 'POST', body: JSON.stringify(req) })
}

export async function provision(config: ProvisionConfig): Promise<{ status: string; run_id: string }> {
  return apiFetch('/api/provision', { method: 'POST', body: JSON.stringify(config) })
}

export async function fetchProvisionStatus(): Promise<ProvisionState> {
  return apiFetch('/api/provision/status')
}

export async function destroyWorkers(): Promise<{ status: string; run_id: string }> {
  return apiFetch('/api/provision/destroy', { method: 'POST' })
}

export async function localRun(req: {
  model_id: string
  capabilities: string[]
  complexity_range: [number, number]
  ollama_url?: string
}): Promise<LocalRunResponse> {
  return apiFetch('/api/local/run', { method: 'POST', body: JSON.stringify(req) })
}
