import { useState } from 'react'
import type { LocalRunResult } from '../types'
import { localRun } from '../api'

const CAPABILITIES = ['invoice_extractor', 'code_generation']

export default function LocalForm() {
  const [modelId, setModelId] = useState('qwen2.5:latest')
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434')
  const [capabilities, setCapabilities] = useState<string[]>(['invoice_extractor'])
  const [complexityMin, setComplexityMin] = useState(1)
  const [complexityMax, setComplexityMax] = useState(5)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<LocalRunResult[] | null>(null)

  const toggleCapability = (cap: string) => {
    setCapabilities((prev) =>
      prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap]
    )
  }

  const handleRun = async () => {
    setError(null)
    setResults(null)
    setRunning(true)
    try {
      const res = await localRun({
        model_id: modelId,
        capabilities,
        complexity_range: [complexityMin, complexityMax],
        ollama_url: ollamaUrl,
      })
      setResults(res.results)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const canRun = modelId.trim().length > 0 && capabilities.length > 0 && !running

  return (
    <div className="form-card">
      <div className="form-section-title">Local Benchmark (Ollama)</div>

      <div className="form-group">
        <label className="form-label">Model</label>
        <input
          className="form-input"
          value={modelId}
          onChange={(e) => setModelId(e.target.value)}
          placeholder="qwen2.5:latest"
        />
        <span className="field-hint">Run <code>ollama list</code> to see available models</span>
      </div>

      <div className="form-group">
        <label className="form-label">Ollama URL</label>
        <input
          className="form-input"
          value={ollamaUrl}
          onChange={(e) => setOllamaUrl(e.target.value)}
          placeholder="http://localhost:11434"
        />
      </div>

      <div className="form-group">
        <label className="form-label">Capabilities</label>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {CAPABILITIES.map((cap) => (
            <label key={cap} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={capabilities.includes(cap)}
                onChange={() => toggleCapability(cap)}
              />
              {cap}
            </label>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Complexity range</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <input
            className="form-input"
            type="number"
            min={1}
            max={5}
            value={complexityMin}
            onChange={(e) => setComplexityMin(Number(e.target.value))}
            style={{ width: '60px' }}
          />
          <span style={{ color: 'var(--text-muted)' }}>to</span>
          <input
            className="form-input"
            type="number"
            min={1}
            max={5}
            value={complexityMax}
            onChange={(e) => setComplexityMax(Number(e.target.value))}
            style={{ width: '60px' }}
          />
        </div>
      </div>

      {error && (
        <div className="text-error" style={{ fontSize: '0.82rem', marginBottom: '0.5rem' }}>
          {error}
        </div>
      )}

      <button className="btn-primary" disabled={!canRun} onClick={handleRun}>
        {running && <span className="spinner" />}
        {running ? 'Running…' : 'Run Benchmark'}
      </button>

      {results && (
        <div style={{ marginTop: '1.5rem' }}>
          <div className="form-section-title">Results</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Capability</th>
                <th style={{ textAlign: 'center', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Complexity</th>
                <th style={{ textAlign: 'center', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Score</th>
                <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Latency</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.3rem 0.5rem' }}>{r.capability}</td>
                  <td style={{ textAlign: 'center', padding: '0.3rem 0.5rem' }}>{r.complexity}</td>
                  <td style={{ textAlign: 'center', padding: '0.3rem 0.5rem' }}>
                    {r.error
                      ? <span className="text-error">error</span>
                      : <span style={{ color: r.score === 1.0 ? 'var(--accent)' : r.score >= 0.5 ? '#f0a500' : 'var(--text-error)' }}>
                          {(r.score * 100).toFixed(0)}%
                        </span>
                    }
                  </td>
                  <td style={{ textAlign: 'right', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>
                    {r.error ? '—' : `${r.latency_ms.toFixed(0)}ms`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Results saved to results/benchmarks.db
          </div>
        </div>
      )}
    </div>
  )
}
