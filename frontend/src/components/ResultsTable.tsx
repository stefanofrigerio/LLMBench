import { useState, useMemo } from 'react'
import type { BenchmarkResult } from '../types'

const CAPABILITIES = [
  '',
  'code_generation',
  'unit_test_writing',
  'text_summarization',
  'data_transformation',
  'reasoning',
  'structured_output',
]

type SortKey = keyof BenchmarkResult
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

export default function ResultsTable({ results }: Props) {
  const [filterCap, setFilterCap] = useState('')
  const [filterModel, setFilterModel] = useState('')
  const [minComplexity, setMinComplexity] = useState(1)
  const [maxComplexity, setMaxComplexity] = useState(5)
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

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
      .slice(0, 100)
  }, [results, filterCap, filterModel, minComplexity, maxComplexity, sortKey, sortDir])

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  function colHeader(label: string, key: SortKey) {
    const active = sortKey === key
    return (
      <th className={active ? 'sorted' : ''} onClick={() => handleSort(key)}>
        {label} {active ? (sortDir === 'asc' ? '↑' : '↓') : ''}
      </th>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">All Results</h3>
        <span className="text-muted" style={{ fontSize: '0.75rem' }}>
          {filtered.length} / {results.length} rows
        </span>
      </div>

      <div className="filter-bar">
        <div className="form-group">
          <label htmlFor="rt-cap">Capability</label>
          <select id="rt-cap" value={filterCap} onChange={(e) => setFilterCap(e.target.value)}>
            {CAPABILITIES.map((c) => (
              <option key={c} value={c}>{c || 'All'}</option>
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
          <input
            id="rt-cmin"
            type="number"
            min={1}
            max={maxComplexity}
            value={minComplexity}
            onChange={(e) => setMinComplexity(Math.max(1, Math.min(maxComplexity, Number(e.target.value))))}
          />
        </div>

        <div className="form-group">
          <label htmlFor="rt-cmax">Max Complexity</label>
          <input
            id="rt-cmax"
            type="number"
            min={minComplexity}
            max={5}
            value={maxComplexity}
            onChange={(e) => setMaxComplexity(Math.max(minComplexity, Math.min(5, Number(e.target.value))))}
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">No results match the current filters.</div>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                {colHeader('Model', 'model_name')}
                {colHeader('Capability', 'capability')}
                {colHeader('Complexity', 'complexity')}
                {colHeader('Score', 'score')}
                {colHeader('Latency (ms)', 'latency_ms')}
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => {
                const pct = Math.round(r.score * 100)
                return (
                  <tr key={i}>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {r.model_name}
                    </td>
                    <td>{r.capability.replace(/_/g, ' ')}</td>
                    <td style={{ textAlign: 'center' }}>{r.complexity}</td>
                    <td>
                      <span className="score-badge" style={scoreStyle(r.score)}>
                        {pct}%
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {r.latency_ms ? Math.round(r.latency_ms) : '—'}
                    </td>
                    <td style={{ color: 'var(--error)', fontSize: '0.7rem' }}>
                      {r.error ? r.error.slice(0, 40) : ''}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
