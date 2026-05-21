import { useState } from 'react'
import type { Worker, QueueStatus, ProvisionState, ProvisionConfig } from '../types'
import GCPForm from './GCPForm'
import BenchmarkConfig from './BenchmarkConfig'
import WorkerGrid from './WorkerGrid'
import BenchmarkProgress from './BenchmarkProgress'
import { provision, destroyWorkers, dispatch } from '../api'

function makeRunId() {
  const now = new Date()
  const pad = (n: number, l = 2) => String(n).padStart(l, '0')
  return `run-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

interface Props {
  workers: Worker[]
  queueStatus: QueueStatus | null
  provisionState: ProvisionState
  onProvisionStateChange: (s: ProvisionState) => void
  runId: string | null
  onRunIdChange: (id: string | null) => void
}

export default function WorkersTab({
  workers,
  queueStatus,
  provisionState,
  onProvisionStateChange,
  runId,
  onRunIdChange,
}: Props) {
  const [provConfig, setProvConfig] = useState<ProvisionConfig>({
    project_id: '',
    run_id: makeRunId(),
    machine_type: 'n1-standard-4',
    worker_count: 1,
    spot: true,
    gpu_type: '',
    models_to_pull: ['deepseek-coder:6.7b', 'qwen2.5-coder:7b'],
    region: 'europe-west1',
    zone: 'europe-west1-b',
    controller_url: '',
  })

  const [capabilities, setCapabilities] = useState<string[]>(['code_generation'])
  const [complexityRange, setComplexityRange] = useState<[number, number]>([1, 3])
  const [provError, setProvError] = useState<string | null>(null)
  const [dispatchError, setDispatchError] = useState<string | null>(null)
  const [dispatchMsg, setDispatchMsg] = useState<string | null>(null)
  const [isDispatching, setIsDispatching] = useState(false)
  const [isProvisioning, setIsProvisioning] = useState(false)
  const [isDestroying, setIsDestroying] = useState(false)

  const canProvision =
    provConfig.project_id.trim().length > 0 &&
    provisionState.status !== 'provisioning' &&
    provisionState.status !== 'destroying'

  const workersReady =
    provisionState.status === 'ready' || workers.length > 0

  const handleProvision = async () => {
    setProvError(null)
    setIsProvisioning(true)
    try {
      const config = { ...provConfig, zone: `${provConfig.region}-b` }
      await provision(config)
      onRunIdChange(config.run_id)
      onProvisionStateChange({
        ...provisionState,
        status: 'provisioning',
        run_id: config.run_id,
        error: null,
      })
    } catch (e: unknown) {
      setProvError(e instanceof Error ? e.message : String(e))
    } finally {
      setIsProvisioning(false)
    }
  }

  const handleDestroy = async () => {
    setProvError(null)
    setIsDestroying(true)
    try {
      await destroyWorkers()
      onProvisionStateChange({ ...provisionState, status: 'destroying' })
    } catch (e: unknown) {
      setProvError(e instanceof Error ? e.message : String(e))
    } finally {
      setIsDestroying(false)
    }
  }

  const handleDispatch = async () => {
    setDispatchError(null)
    setDispatchMsg(null)
    setIsDispatching(true)
    try {
      const activeRunId = runId ?? provConfig.run_id
      const models = provConfig.models_to_pull.map((m) => ({
        name: m,
        provider: 'ollama',
        model_id: m,
      }))
      const res = await dispatch({
        run_id: activeRunId,
        models,
        capabilities,
        complexity_range: complexityRange,
      })
      setDispatchMsg(`Dispatched ${res.total_tasks} tasks to ${res.active_workers} workers.`)
    } catch (e: unknown) {
      setDispatchError(e instanceof Error ? e.message : String(e))
    } finally {
      setIsDispatching(false)
    }
  }

  return (
    <div className="two-col">
      <div className="left-panel">
        <GCPForm value={provConfig} onChange={setProvConfig} />
        <BenchmarkConfig
          capabilities={capabilities}
          onCapabilitiesChange={setCapabilities}
          complexityRange={complexityRange}
          onComplexityRangeChange={setComplexityRange}
          runId={runId ?? provConfig.run_id}
        />

        {provError && (
          <div className="text-error" style={{ fontSize: '0.8rem' }}>
            Error: {provError}
          </div>
        )}
        {dispatchError && (
          <div className="text-error" style={{ fontSize: '0.8rem' }}>
            Dispatch error: {dispatchError}
          </div>
        )}
        {dispatchMsg && (
          <div className="text-success" style={{ fontSize: '0.8rem' }}>
            {dispatchMsg}
          </div>
        )}

        <div className="button-row">
          <button
            className="btn-primary"
            disabled={!canProvision || isProvisioning}
            onClick={handleProvision}
          >
            {isProvisioning && <span className="spinner" />}
            Provision Workers
          </button>

          <button
            className="btn-primary"
            disabled={!workersReady || isDispatching || capabilities.length === 0}
            onClick={handleDispatch}
          >
            {isDispatching && <span className="spinner" />}
            Start Benchmark
          </button>
        </div>

        {provisionState.status === 'ready' && (
          <div>
            <button
              className="btn-danger"
              disabled={isDestroying}
              onClick={handleDestroy}
              style={{ fontSize: '0.8rem' }}
            >
              {isDestroying && <span className="spinner" />}
              Destroy Workers
            </button>
          </div>
        )}
      </div>

      <div className="right-panel">
        <WorkerGrid workers={workers} provisionState={provisionState} />
        <BenchmarkProgress status={queueStatus} />
      </div>
    </div>
  )
}
