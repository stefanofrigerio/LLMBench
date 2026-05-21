import { useState, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { fetchWorkers, fetchStatus, fetchProvisionStatus } from './api'
import type { Worker, QueueStatus, ProvisionState } from './types'
import WorkersTab from './components/WorkersTab'
import ResultsTab from './components/ResultsTab'

type Tab = 'workers' | 'results'

const WS_URL =
  typeof window !== 'undefined'
    ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/dashboard`
    : 'ws://localhost:8000/ws/dashboard'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('workers')
  const [workers, setWorkers] = useState<Worker[]>([])
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null)
  const [provisionState, setProvisionState] = useState<ProvisionState>({
    status: 'idle',
    logs: [],
    worker_ips: [],
    error: null,
    run_id: null,
  })
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)

  const { lastMessage, readyState } = useWebSocket(WS_URL)

  // Poll basic state on mount
  useEffect(() => {
    const load = async () => {
      try {
        const [wRes, sRes, pRes] = await Promise.all([
          fetchWorkers(),
          fetchStatus(),
          fetchProvisionStatus(),
        ])
        setWorkers(wRes.workers)
        setQueueStatus(sRes.queue_status)
        setCurrentRunId(sRes.run_id)
        setProvisionState(pRes)
      } catch {
        // backend may not be up yet
      }
    }
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return
    try {
      const msg = JSON.parse(lastMessage.data as string)
      if (msg.type === 'status_update' || msg.type === 'status') {
        if (msg.data.queue_status) setQueueStatus(msg.data.queue_status)
      }
      if (msg.type === 'workers_update' || msg.type === 'status') {
        if (msg.data.workers) setWorkers(msg.data.workers)
      }
      if (msg.type === 'provision_update') {
        setProvisionState(msg.data as ProvisionState)
      }
    } catch {
      // ignore parse errors
    }
  }, [lastMessage])

  const isConnected = readyState === 1

  return (
    <div className="app">
      <header className="header">
        <span className="header-title">LLMBench</span>
        <span className="header-subtitle">Distributed LLM Benchmark System</span>
        <div className="ws-indicator">
          <span className={`ws-dot${isConnected ? ' connected' : ''}`} />
          {isConnected ? 'Live' : 'Disconnected'}
        </div>
      </header>

      <div className="main-content">
        <div className="tabs">
          <button
            className={`tab${activeTab === 'workers' ? ' active' : ''}`}
            onClick={() => setActiveTab('workers')}
          >
            Workers
          </button>
          <button
            className={`tab${activeTab === 'results' ? ' active' : ''}`}
            onClick={() => setActiveTab('results')}
          >
            Results
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'workers' && (
            <WorkersTab
              workers={workers}
              queueStatus={queueStatus}
              provisionState={provisionState}
              onProvisionStateChange={setProvisionState}
              runId={currentRunId}
              onRunIdChange={setCurrentRunId}
            />
          )}
          {activeTab === 'results' && <ResultsTab />}
        </div>
      </div>
    </div>
  )
}
