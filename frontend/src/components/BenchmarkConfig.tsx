const ALL_CAPABILITIES = [
  'code_generation',
  'unit_test_writing',
  'text_summarization',
  'data_transformation',
  'reasoning',
  'structured_output',
]

interface Props {
  capabilities: string[]
  onCapabilitiesChange: (caps: string[]) => void
  complexityRange: [number, number]
  onComplexityRangeChange: (range: [number, number]) => void
  runId: string
}

export default function BenchmarkConfig({
  capabilities,
  onCapabilitiesChange,
  complexityRange,
  onComplexityRangeChange,
  runId,
}: Props) {
  function toggleCap(cap: string) {
    const next = capabilities.includes(cap)
      ? capabilities.filter((c) => c !== cap)
      : [...capabilities, cap]
    onCapabilitiesChange(next)
  }

  return (
    <div className="card stack">
      <h3 className="card-title">Benchmark Configuration</h3>

      <div className="form-group">
        <label>Capabilities</label>
        <div className="checkbox-group">
          {ALL_CAPABILITIES.map((cap) => (
            <label key={cap} className="checkbox-item">
              <input
                type="checkbox"
                checked={capabilities.includes(cap)}
                onChange={() => toggleCap(cap)}
              />
              {cap.replace(/_/g, ' ')}
            </label>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label>Complexity Range</label>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="cmin">Min</label>
            <input
              id="cmin"
              type="number"
              min={1}
              max={complexityRange[1]}
              value={complexityRange[0]}
              onChange={(e) => {
                const v = Math.max(1, Math.min(complexityRange[1], Number(e.target.value)))
                onComplexityRangeChange([v, complexityRange[1]])
              }}
            />
          </div>
          <div className="form-group">
            <label htmlFor="cmax">Max</label>
            <input
              id="cmax"
              type="number"
              min={complexityRange[0]}
              max={5}
              value={complexityRange[1]}
              onChange={(e) => {
                const v = Math.max(complexityRange[0], Math.min(5, Number(e.target.value)))
                onComplexityRangeChange([complexityRange[0], v])
              }}
            />
          </div>
        </div>
      </div>

      {runId && (
        <div className="form-group">
          <label>Run ID</label>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
            {runId}
          </span>
        </div>
      )}
    </div>
  )
}
