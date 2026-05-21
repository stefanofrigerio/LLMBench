import { useState } from 'react'
import type { ProvisionConfig } from '../types'

interface Props {
  value: ProvisionConfig
  onChange: (c: ProvisionConfig) => void
}

const MACHINE_TYPES = ['n1-standard-4', 'n1-standard-8', 'n1-highmem-8']
const GPU_OPTIONS = ['', 'nvidia-tesla-t4', 'nvidia-tesla-v100']
const ALL_MODELS = [
  'deepseek-coder:6.7b',
  'qwen2.5-coder:7b',
  'llama3.1:8b',
  'codellama:7b',
]

export default function GCPForm({ value, onChange }: Props) {
  const [open, setOpen] = useState(true)

  function set<K extends keyof ProvisionConfig>(key: K, val: ProvisionConfig[K]) {
    onChange({ ...value, [key]: val })
  }

  function toggleModel(model: string) {
    const next = value.models_to_pull.includes(model)
      ? value.models_to_pull.filter((m) => m !== model)
      : [...value.models_to_pull, model]
    set('models_to_pull', next)
  }

  return (
    <div className="card">
      <button className="collapsible-trigger" onClick={() => setOpen((o) => !o)}>
        <span>Provision Workers (GCP)</span>
        <span className={`collapsible-arrow${open ? ' open' : ''}`}>&#9660;</span>
      </button>

      {open && (
        <div className="collapsible-body stack">
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="gcp-project">GCP Project ID *</label>
              <input
                id="gcp-project"
                type="text"
                placeholder="my-gcp-project"
                value={value.project_id}
                onChange={(e) => set('project_id', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="gcp-runid">Run ID</label>
              <input
                id="gcp-runid"
                type="text"
                placeholder="run-YYYYMMDD-HHMMSS"
                value={value.run_id}
                onChange={(e) => set('run_id', e.target.value)}
              />
            </div>
          </div>

          <div className="section-divider">Tailscale</div>

          <div className="form-group">
            <label htmlFor="gcp-ts-key">
              Auth Key *
              <a
                href="https://login.tailscale.com/admin/settings/keys"
                target="_blank"
                rel="noreferrer"
                className="label-hint"
              >
                Generate →
              </a>
            </label>
            <input
              id="gcp-ts-key"
              type="password"
              placeholder="tskey-auth-..."
              value={value.tailscale_auth_key}
              onChange={(e) => set('tailscale_auth_key', e.target.value)}
            />
            <span className="field-hint">Reusable + Ephemeral. Workers auto-remove from tailnet on shutdown.</span>
          </div>

          <div className="form-group">
            <label htmlFor="gcp-controller">Controller URL *</label>
            <input
              id="gcp-controller"
              type="text"
              placeholder="http://100.x.x.x:8000"
              value={value.controller_url}
              onChange={(e) => set('controller_url', e.target.value)}
            />
            <span className="field-hint">Your Tailscale IP — run <code>tailscale ip -4</code> to get it.</span>
          </div>

          <div className="section-divider">Machine</div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="gcp-machine">Machine Type</label>
              <select
                id="gcp-machine"
                value={value.machine_type}
                onChange={(e) => set('machine_type', e.target.value)}
              >
                {MACHINE_TYPES.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="gcp-workers">Worker Count</label>
              <input
                id="gcp-workers"
                type="number"
                min={1}
                max={5}
                value={value.worker_count}
                onChange={(e) => set('worker_count', Math.max(1, Math.min(5, Number(e.target.value))))}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="gcp-gpu">GPU</label>
              <select
                id="gcp-gpu"
                value={value.gpu_type}
                onChange={(e) => set('gpu_type', e.target.value)}
              >
                {GPU_OPTIONS.map((g) => (
                  <option key={g} value={g}>{g || 'None (CPU only)'}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="gcp-region">Region</label>
              <input
                id="gcp-region"
                type="text"
                value={value.region}
                onChange={(e) => set('region', e.target.value)}
              />
            </div>
          </div>

          <div className="form-group toggle-row">
            <input
              id="gcp-spot"
              type="checkbox"
              checked={value.spot}
              onChange={(e) => set('spot', e.target.checked)}
            />
            <label htmlFor="gcp-spot" style={{ textTransform: 'none', letterSpacing: 0 }}>
              Use spot instance (~70% cheaper, may be preempted)
            </label>
          </div>

          <div className="section-divider">Models</div>

          <div className="form-group">
            <div className="checkbox-group">
              {ALL_MODELS.map((m) => (
                <label key={m} className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={value.models_to_pull.includes(m)}
                    onChange={() => toggleModel(m)}
                  />
                  {m}
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
