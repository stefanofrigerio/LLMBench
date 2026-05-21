export interface Worker {
  worker_id: string
  ip_address: string
  status: 'idle' | 'busy' | 'offline'
  current_task_id: string | null
  tasks_completed: number
  tasks_failed: number
  last_heartbeat: string
}

export interface QueueStatus {
  total_enqueued: number
  queued: number
  pending: number
  completed: number
  failed: number
  completion_rate: number
}

export interface BenchmarkResult {
  model_name: string
  capability: string
  complexity: number
  score: number
  latency_ms: number
  cost_estimate: number
  error: string | null
}

export interface ScoreEntry {
  model_name: string
  avg_score: number
  avg_latency: number
  avg_cost: number
  sample_count: number
}

export interface Recommendation {
  model_name: string
  avg_score: number
  avg_latency: number
  sample_count: number
  min_score_threshold: number
  sensitivity: number
}

export interface ProvisionState {
  status: 'idle' | 'provisioning' | 'ready' | 'destroying' | 'error'
  logs: string[]
  worker_ips: string[]
  error: string | null
  run_id: string | null
}

export interface ProvisionConfig {
  project_id: string
  run_id: string
  tailscale_auth_key: string
  controller_url: string        // http://<tailscale-ip>:8000
  machine_type: string
  worker_count: number
  spot: boolean
  gpu_type: string
  models_to_pull: string[]
  region: string
  zone: string
}
