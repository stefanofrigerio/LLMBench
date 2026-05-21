import type { Worker, ProvisionState } from '../types'

interface Props {
  workers: Worker[]
  provisionState: ProvisionState
}

function statusBadge(status: Worker['status']) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

function truncate(s: string | null, len = 20): string {
  if (!s) return '—'
  return s.length > len ? s.slice(0, len) + '…' : s
}

export default function WorkerGrid({ workers, provisionState }: Props) {
  const showBanner =
    provisionState.status === 'provisioning' || provisionState.status === 'destroying'

  const recentLogs = provisionState.logs.slice(-5)

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">Workers</h3>
        <span className={`badge badge-${provisionState.status}`}>
          {provisionState.status}
        </span>
      </div>

      {showBanner && (
        <div className="provision-banner">
          <div className="provision-banner-title">
            <span className="spinner" />
            {provisionState.status === 'provisioning' ? 'Provisioning workers…' : 'Destroying workers…'}
          </div>
          <div className="provision-log">
            {recentLogs.length === 0 ? (
              <span className="text-muted">Waiting for output…</span>
            ) : (
              recentLogs.map((line, i) => (
                <div key={i} className="provision-log-line">{line}</div>
              ))
            )}
          </div>
        </div>
      )}

      {provisionState.status === 'error' && provisionState.error && (
        <div className="provision-banner" style={{ borderColor: 'var(--error)' }}>
          <div className="provision-banner-title" style={{ color: 'var(--error)' }}>
            Provision error
          </div>
          <div className="provision-log">
            <div className="provision-log-line text-error">{provisionState.error}</div>
          </div>
        </div>
      )}

      {provisionState.worker_ips.length > 0 && (
        <div style={{ marginBottom: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Worker IPs: {provisionState.worker_ips.join(', ')}
        </div>
      )}

      {workers.length === 0 ? (
        <div className="empty-state">No workers registered yet.</div>
      ) : (
        <div className="worker-grid">
          {workers.map((w) => (
            <div key={w.worker_id} className="worker-card">
              <div className="row-center">
                {statusBadge(w.status)}
              </div>
              <div className="worker-id" title={w.worker_id}>{w.worker_id}</div>
              <div className="worker-task" title={w.current_task_id ?? undefined}>
                {truncate(w.current_task_id)}
              </div>
              <div className="worker-counts">
                <span>{w.tasks_completed} done</span>
                {w.tasks_failed > 0 && <span className="failed">{w.tasks_failed} failed</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
