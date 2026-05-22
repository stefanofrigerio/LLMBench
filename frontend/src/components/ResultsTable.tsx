import { useState, useMemo } from 'react'
import type { BenchmarkResult } from '../types'
import { useCapabilities } from '../hooks/useCapabilities'

type SortKey = 'model_name' | 'capability' | 'complexity' | 'score' | 'latency_ms' | 'timestamp'
type SortDir = 'asc' | 'desc'

interface Props {
  results: BenchmarkResult[]
}

function scoreStyle(score: number) {
  if (score >= 0.9) return { background: 'rgba(34,197,94,0.2)', color: '#4ade80' }
  if (score >= 0.8) return { background: 'rgba(34,197,94,0.1)', color: '#86efac' }
  if (score >= 0.7) return { background: 'rgba(245,158,11,0.15)', color: '#fcd34d' }
  if (score >= 0.6) return { background: 'rgba(245,158,11,0.1)', color: '#fde68a' }
  return { background: 'rgba(239,68,68,0.15)', color: '#fca5a5' }
}

function tryPrettyJson(text: string | null): string {
  if (!text) return ''
  try { return JSON.stringify(JSON.parse(text), null, 2) }
  catch { return text }
}

function OutputPane({ label, text }: { label: string; text: string | null }) {
  if (!text) return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>{label}</div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>—</div>
    </div>
  )
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.3rem', fontWeight: 600 }}>{label}</div>
      <pre style={{
        margin: 0,
        fontSize: '0.72rem',
        lineHeight: 1.45,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: '4px',
        padding: '0.5rem',
        maxHeight: '260px',
        overflowY: 'auto',
        color: 'var(--text)',
      }}>
        {tryPrettyJson(text)}
      </pre>
    </div>
  )
}

export default function ResultsTable({ results }: Props) {
  const capabilities = useCapabilities()
  const [filterCap, setFilterCap] = useState('')
  const [filterModel, setFilterModel] = useState('')
  const [minComplexity, setMinComplexity] = useState(1)
  const [maxComplexity, setMaxComplexity] = useState(5)
  const [sortKey, setSortKey] = useState<SortKey>('timestamp')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const modelNames = useMemo(
    () => Array.from(new Set(results.map((r) => r.model_name))).sort(),
    [results],
  )

  const filtered = useMemo(() => {
    return results
      .filter((r) => {
        if (filterCap && r.capability !== filterCap) return false
        if (filterModel && r.model_name !== filterModel) return false
        if (r.complexity < minComplexity || r.complexity > maxComplexity) return false
        return true
      })
      .sort((a, b) => {
        const av = a[sortKey] ?? 0
        const bv = b[sortKey] ?? 0
        const cmp = av < bv ? -1 : av > bv ? 1 : 0
        return sortDir === 'asc' ? cmp : -cmp
      })
      .slice(0, 200)
  }, [results, filterCap, filterModel, minComplexity, maxComplexity, sortKey, sortDir])

  function handleSort(key: SortKey) {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  function colHeader(label: string, key: SortKey) {
    const active = sortKey === key
    return (
      <th className={active ? 'sorted' : ''} onClick={() => handleSort(key)} style={{ cursor: 'pointer', userSelect: 'none' }}>
        {label} {active ? (sortDir === 'asc' ? '↑' : '↓') : ''}
      </th>
    )
  }

  function toggleExpand(id: number) {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">All Results</h3>
        <span className="text-muted" style={{ fontSize: '0.75rem' }}>
          {filtered.length} / {results.length} rows — click a row to inspect output
        </span>
      </div>

      <div className="filter-bar">
        <div className="form-group">
          <label htmlFor="rt-cap">Capability</label>
          <select id="rt-cap" value={filterCap} onChange={(e) => setFilterCap(e.target.value)}>
            <option value="">All</option>
            {capabilities.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="rt-model">Model</label>
          <select id="rt-model" value={filterModel} onChange={(e) => setFilterModel(e.target.value)}>
            <option value="">All</option>
            {modelNames.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="rt-cmin">Min Complexity</label>
          <input id="rt-cmin" type="number" min={1} max={maxComplexity} value={minComplexity}
            onChange={(e) => setMinComplexity(Math.max(1, Math.min(maxComplexity, Number(e.target.value))))} />
        </div>

        <div className="form-group">
          <label htmlFor="rt-cmax">Max Complexity</label>
          <input id="rt-cmax" type="number" min={minComplexity} max={5} value={maxComplexity}
            onChange={(e) => setMaxComplexity(Math.max(minComplexity, Math.min(5, Number(e.target.value))))} />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">No results match the current filters.</div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th style={{ width: '1.5rem' }} />
                {colHeader('Model', 'model_name')}
                {colHeader('Capability', 'capability')}
                {colHeader('Complexity', 'complexity')}
                {colHeader('Score', 'score')}
                {colHeader('Latency (ms)', 'latency_ms')}
                {colHeader('Time', 'timestamp')}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const pct = Math.round(r.score * 100)
                const isExpanded = expandedId === r.id
                const hasOutput = r.raw_output || r.expected_output
                return (
                  <>
                    <tr
                      key={r.id}
                      onClick={() => hasOutput && toggleExpand(r.id)}
                      style={{ cursor: hasOutput ? 'pointer' : 'default', background: isExpanded ? 'var(--surface)' : undefined }}
                    >
                      <td style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                        {hasOutput ? (isExpanded ? '▼' : '▶') : ''}
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{r.model_name}</td>
                      <td>{r.capability.replace(/_/g, ' ')}</td>
                      <td style={{ textAlign: 'center' }}>{r.complexity}</td>
                      <td>
                        <span className="score-badge" style={scoreStyle(r.score)}>{pct}%</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {r.latency_ms ? Math.round(r.latency_ms) : '—'}
                      </td>
                      <td style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {r.timestamp ? r.timestamp.replace('T', ' ').slice(0, 19) : ''}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${r.id}-detail`} style={{ background: 'var(--surface)' }}>
                        <td colSpan={7} style={{ padding: '0.75rem 1rem 1rem' }}>
                          {r.error && (
                            <div style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'var(--text-error)' }}>
                              <strong>Error:</strong> {r.error}
                            </div>
                          )}
                          <div style={{ display: 'flex', gap: '1rem' }}>
                            <OutputPane label="LLM output" text={r.raw_output} />
                            <OutputPane label="Expected" text={r.expected_output} />
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
