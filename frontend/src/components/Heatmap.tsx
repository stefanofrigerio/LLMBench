import { useState, useEffect, useCallback } from 'react'
import { fetchResults, fetchScores } from '../api'
import type { ScoreEntry } from '../types'
import { useCapabilities } from '../hooks/useCapabilities'

const COMPLEXITIES = [1, 2, 3, 4, 5]

function scoreColor(score: number | null): string {
  if (score === null) return 'var(--surface-2)'
  if (score < 0.6) return '#7f1d1d'
  if (score < 0.7) return '#92400e'
  if (score < 0.8) return '#713f12'
  if (score < 0.9) return '#14532d'
  return '#166534'
}

function scoreTextColor(score: number | null): string {
  if (score === null) return 'var(--text-muted)'
  return '#fff'
}

type ScoreMap = Record<string, Record<number, number | null>>

export default function Heatmap() {
  const capabilities = useCapabilities()
  const [modelNames, setModelNames] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [scoreMap, setScoreMap] = useState<ScoreMap>({})
  const [loading, setLoading] = useState(false)

  // Fetch all distinct model names
  useEffect(() => {
    fetchResults()
      .then((res) => {
        const names = Array.from(new Set(res.results.map((r) => r.model_name)))
        setModelNames(names)
        if (names.length > 0 && !selectedModel) setSelectedModel(names[0])
      })
      .catch(() => {})
  }, [selectedModel])

  const loadScores = useCallback(async (model: string) => {
    if (!model) return
    setLoading(true)
    const newMap: ScoreMap = {}

    await Promise.all(
      capabilities.map(async (cap) => {
        newMap[cap] = {}
        for (const comp of COMPLEXITIES) {
          newMap[cap][comp] = null
        }
        await Promise.all(
          COMPLEXITIES.map(async (comp) => {
            try {
              const res = await fetchScores(cap, comp)
              const entry = res.models.find(
                (m: ScoreEntry) => m.model_name === model,
              )
              if (entry) newMap[cap][comp] = entry.avg_score
            } catch {
              // no data
            }
          }),
        )
      }),
    )

    setScoreMap(newMap)
    setLoading(false)
  }, [])

  useEffect(() => {
    if (selectedModel) loadScores(selectedModel)
  }, [selectedModel, loadScores])

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">Performance Heatmap</h3>
        {loading && <span className="spinner" />}
      </div>

      <div className="model-selector-row">
        <div className="form-group">
          <label htmlFor="heatmap-model">Model</label>
          <select
            id="heatmap-model"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={modelNames.length === 0}
          >
            {modelNames.length === 0 ? (
              <option value="">No models yet</option>
            ) : (
              modelNames.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))
            )}
          </select>
        </div>
      </div>

      {modelNames.length === 0 ? (
        <div className="empty-state">No benchmark results yet.</div>
      ) : (
        <>
          <div className="heatmap-wrapper">
            <table className="heatmap-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', paddingRight: '1rem', minWidth: '130px' }}>
                    Capability
                  </th>
                  {COMPLEXITIES.map((c) => (
                    <th key={c} style={{ textAlign: 'center' }}>
                      Complexity {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {capabilities.map((cap) => (
                  <tr key={cap}>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)', paddingRight: '1rem' }}>
                      {cap.replace(/_/g, ' ')}
                    </td>
                    {COMPLEXITIES.map((comp) => {
                      const score = scoreMap[cap]?.[comp] ?? null
                      const pct = score !== null ? Math.round(score * 100) : null
                      return (
                        <td
                          key={comp}
                          style={{ textAlign: 'center', padding: '2px' }}
                        >
                          <div
                            className="tooltip-wrapper"
                            style={{ display: 'inline-block', width: '100%' }}
                          >
                            <div
                              className={`heatmap-cell${score === null ? ' heatmap-no-data' : ''}`}
                              style={{
                                backgroundColor: scoreColor(score),
                                color: scoreTextColor(score),
                              }}
                            >
                              {pct !== null ? `${pct}%` : '—'}
                            </div>
                            <span className="tooltip-text">
                              {cap} / complexity {comp}
                              {pct !== null ? `: ${pct}%` : ': no data'}
                            </span>
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="legend">
            <span className="text-muted" style={{ fontSize: '0.7rem', marginRight: '0.25rem' }}>
              Score:
            </span>
            {[
              { color: '#7f1d1d', label: '<60%' },
              { color: '#92400e', label: '60-70%' },
              { color: '#713f12', label: '70-80%' },
              { color: '#14532d', label: '80-90%' },
              { color: '#166534', label: '≥90%' },
              { color: 'var(--surface-2)', label: 'No data' },
            ].map(({ color, label }) => (
              <div key={label} className="legend-item">
                <div className="legend-swatch" style={{ background: color, border: '1px solid var(--border)' }} />
                {label}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
