import type { QueueStatus } from '../types'

interface Props {
  status: QueueStatus | null
}

export default function BenchmarkProgress({ status }: Props) {
  if (!status) {
    return (
      <div className="card">
        <h3 className="card-title" style={{ marginBottom: '1rem' }}>Benchmark Progress</h3>
        <div className="empty-state">No benchmark running.</div>
      </div>
    )
  }

  const { total_enqueued, completed, queued, pending, failed, completion_rate } = status
  const pct = Math.round((completion_rate ?? 0) * 100)
  const isDone = total_enqueued > 0 && completed >= total_enqueued

  return (
    <div className="card">
      <h3 className="card-title" style={{ marginBottom: '1rem' }}>Benchmark Progress</h3>

      <div className="progress-stats">
        <div className="stat-item">
          <span className="stat-value">{completed}</span>
          <span className="stat-label">Completed</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{total_enqueued}</span>
          <span className="stat-label">Total</span>
        </div>
        <div className="stat-item">
          <span className="stat-value" style={{ fontSize: '1.1rem' }}>{pct}%</span>
          <span className="stat-label">Done</span>
        </div>
      </div>

      <div style={{ marginTop: '0.875rem' }}>
        <div className="progress-container">
          <div className="progress-bar" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          gap: '1.5rem',
          marginTop: '0.75rem',
          fontSize: '0.8rem',
          color: 'var(--text-muted)',
        }}
      >
        <span>Queued: <strong style={{ color: 'var(--text)' }}>{queued}</strong></span>
        <span>Pending: <strong style={{ color: 'var(--warning)' }}>{pending}</strong></span>
        {failed > 0 && (
          <span>Failed: <strong style={{ color: 'var(--error)' }}>{failed}</strong></span>
        )}
      </div>

      {isDone && (
        <div className="complete-message">Benchmark complete</div>
      )}
    </div>
  )
}
