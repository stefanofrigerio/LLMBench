import { useState } from 'react'
import { recommend } from '../api'
import type { Recommendation } from '../types'

const CAPABILITIES = [
  'code_generation',
  'unit_test_writing',
  'text_summarization',
  'data_transformation',
  'reasoning',
  'structured_output',
]

const SENSITIVITY_LABELS: Record<number, string> = {
  1: '60%',
  2: '70%',
  3: '80%',
  4: '90%',
  5: '95%',
}

export default function RecommendWidget() {
  const [capability, setCapability] = useState('code_generation')
  const [complexity, setComplexity] = useState(3)
  const [sensitivity, setSensitivity] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<Recommendation | null | undefined>(undefined)
  const [noMatch, setNoMatch] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFind = async () => {
    setLoading(true)
    setError(null)
    setResult(undefined)
    setNoMatch(false)
    try {
      const res = await recommend(capability, complexity, sensitivity)
      if (res.recommendation) {
        setResult(res.recommendation)
        setNoMatch(false)
      } else {
        setResult(null)
        setNoMatch(true)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const scorePct = result ? Math.round(result.avg_score * 100) : 0

  return (
    <div className="card">
      <h3 className="card-title" style={{ marginBottom: '1rem' }}>Model Recommendation</h3>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="rec-cap">Capability</label>
          <select
            id="rec-cap"
            value={capability}
            onChange={(e) => setCapability(e.target.value)}
          >
            {CAPABILITIES.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="rec-complexity">Complexity</label>
          <select
            id="rec-complexity"
            value={complexity}
            onChange={(e) => setComplexity(Number(e.target.value))}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="form-group" style={{ marginTop: '0.5rem' }}>
        <label htmlFor="rec-sens">
          Sensitivity — min score threshold: {SENSITIVITY_LABELS[sensitivity]}
        </label>
        <select
          id="rec-sens"
          value={sensitivity}
          onChange={(e) => setSensitivity(Number(e.target.value))}
        >
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>{n} — min {SENSITIVITY_LABELS[n]}</option>
          ))}
        </select>
      </div>

      <div style={{ marginTop: '0.75rem' }}>
        <button className="btn-primary" onClick={handleFind} disabled={loading}>
          {loading && <span className="spinner" />}
          Find Best Model
        </button>
      </div>

      {error && (
        <div className="text-error" style={{ marginTop: '0.75rem', fontSize: '0.8rem' }}>
          {error}
        </div>
      )}

      {noMatch && !loading && (
        <div className="recommend-result">
          <div className="recommend-no-model">
            No open-source model meets this requirement — use a proprietary model
          </div>
          <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: '0.375rem' }}>
            Minimum score threshold for sensitivity={sensitivity}: {SENSITIVITY_LABELS[sensitivity]}
          </div>
        </div>
      )}

      {result && !loading && (
        <div className="recommend-result">
          <div className="recommend-model-name">{result.model_name}</div>

          <div className="score-bar-wrapper">
            <div
              className="score-bar-fill"
              style={{ width: `${scorePct}%` }}
            />
          </div>

          <div className="recommend-meta">
            <span>Score: <strong>{scorePct}%</strong></span>
            <span>Latency: <strong>{Math.round(result.avg_latency)} ms</strong></span>
            <span>Samples: <strong>{result.sample_count}</strong></span>
          </div>

          <div
            style={{
              marginTop: '0.5rem',
              fontSize: '0.75rem',
              color: 'var(--success)',
            }}
          >
            Meets minimum score {SENSITIVITY_LABELS[sensitivity]} for sensitivity={sensitivity}
          </div>
        </div>
      )}
    </div>
  )
}
