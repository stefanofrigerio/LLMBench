import { useEffect, useState } from 'react'
import type { LocalRunResult } from '../types'
import { localRun, fetchCapabilities, fetchOllamaModels } from '../api'

export default function LocalForm() {
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434')

  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [selectedModels, setSelectedModels] = useState<string[]>([])

  const [availableCaps, setAvailableCaps] = useState<string[]>([])
  const [capabilities, setCapabilities] = useState<string[]>([])

  const [complexityMin, setComplexityMin] = useState(1)
  const [complexityMax, setComplexityMax] = useState(5)
  const [running, setRunning] = useState(false)
  const [runningModel, setRunningModel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<LocalRunResult[] | null>(null)

  // Load capabilities once on mount
  useEffect(() => {
    fetchCapabilities()
      .then(({ capabilities: caps }) => {
        setAvailableCaps(caps)
        setCapabilities(caps)
      })
      .catch(() => {})
  }, [])

  // Load Ollama models whenever URL changes (debounced)
  useEffect(() => {
    setModelsError(null)
    const timer = setTimeout(() => {
      fetchOllamaModels(ollamaUrl)
        .then(({ models, error: err }) => {
          if (err) {
            setModelsError(err)
            setAvailableModels([])
          } else {
            setAvailableModels(models)
            setSelectedModels(models) // select all by default
          }
        })
        .catch((e) => setModelsError(String(e)))
    }, 500)
    return () => clearTimeout(timer)
  }, [ollamaUrl])

  const toggleModel = (m: string) =>
    setSelectedModels((prev) => prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m])

  const toggleCap = (cap: string) =>
    setCapabilities((prev) => prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap])

  const handleRun = async () => {
    setError(null)
    setResults(null)
    setRunning(true)
    const allResults: LocalRunResult[] = []
    try {
      for (const model of selectedModels) {
        setRunningModel(model)
        const res = await localRun({
          model_id: model,
          capabilities,
          complexity_range: [complexityMin, complexityMax],
          ollama_url: ollamaUrl,
        })
        allResults.push(...res.results)
      }
      setResults(allResults)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
      setRunningModel(null)
    }
  }

  const canRun = selectedModels.length > 0 && capabilities.length > 0 && !running

  return (
    <div className="form-card">
      <div className="form-section-title">Local Benchmark (Ollama)</div>

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
        <label className="form-label">Models</label>
        {modelsError && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-error)' }}>
            Ollama not reachable: {modelsError}
          </span>
        )}
        {!modelsError && availableModels.length === 0 && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Connecting to Ollama…
          </span>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
          {availableModels.map((m) => (
            <label key={m} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={selectedModels.includes(m)}
                onChange={() => toggleModel(m)}
              />
              <code style={{ fontSize: '0.82rem' }}>{m}</code>
            </label>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Capabilities</label>
        {availableCaps.length === 0 ? (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Loading…</span>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            {availableCaps.map((cap) => (
              <label key={cap} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={capabilities.includes(cap)}
                  onChange={() => toggleCap(cap)}
                />
                {cap.replace(/_/g, ' ')}
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="form-group">
        <label className="form-label">Complexity range</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <input
            className="form-input"
            type="number" min={1} max={5}
            value={complexityMin}
            onChange={(e) => setComplexityMin(Number(e.target.value))}
            style={{ width: '60px' }}
          />
          <span style={{ color: 'var(--text-muted)' }}>to</span>
          <input
            className="form-input"
            type="number" min={1} max={5}
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
        {running ? `Running ${runningModel}…` : 'Run Benchmark'}
      </button>

      {results && results.length > 0 && (
        <div style={{ marginTop: '1.5rem' }}>
          <div className="form-section-title">Results</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Model</th>
                <th style={{ textAlign: 'left', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Capability</th>
                <th style={{ textAlign: 'center', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Complexity</th>
                <th style={{ textAlign: 'center', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Score</th>
                <th style={{ textAlign: 'right', padding: '0.3rem 0.5rem', color: 'var(--text-muted)' }}>Latency</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.3rem 0.5rem' }}><code style={{ fontSize: '0.8rem' }}>{r.model_name}</code></td>
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
