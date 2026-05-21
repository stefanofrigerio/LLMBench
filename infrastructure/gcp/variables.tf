# ---------------------------------------------------------------------------
# Required
# ---------------------------------------------------------------------------

variable "project_id" {
  description = "GCP project ID (gcloud config set project <ID>)"
  type        = string
}

variable "run_id" {
  description = "Unique identifier for this benchmark run (e.g. run-20250521)"
  type        = string
}

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "europe-west1-b"
}

# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------

variable "machine_type" {
  description = "Compute Engine machine type"
  type        = string
  default     = "n1-standard-4"
}

variable "disk_size_gb" {
  description = "Boot disk size in GB (models can be several GB each)"
  type        = number
  default     = 100
}

variable "spot" {
  description = "Use Spot (preemptible) instances for ~60-80% cost reduction"
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# GPU (optional)
# ---------------------------------------------------------------------------

variable "gpu_type" {
  description = "GPU accelerator type. Empty string = CPU-only. Example: nvidia-tesla-t4"
  type        = string
  default     = ""
}

variable "gpu_count" {
  description = "Number of GPUs to attach (only used when gpu_type is set)"
  type        = number
  default     = 1
}

# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

variable "worker_count" {
  description = "Number of worker VMs to provision in parallel"
  type        = number
  default     = 1
}

# ---------------------------------------------------------------------------
# Benchmark configuration
# ---------------------------------------------------------------------------

variable "models_to_pull" {
  description = "Ollama model tags to pull on each worker at boot time"
  type        = list(string)
  default = [
    "deepseek-coder:6.7b",
    "qwen2.5-coder:7b",
    "llama3.1:8b",
  ]
}

variable "controller_url" {
  description = "HTTP URL of the LLMBench controller (workers register here). Empty = standalone mode"
  type        = string
  default     = ""
}

variable "repo_url" {
  description = "Git repository URL to clone on workers (HTTPS, no auth required for public repos)"
  type        = string
  default     = "https://github.com/stefanofrigerio/LLMBench.git"
}

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

variable "allowed_ssh_cidrs" {
  description = "CIDR ranges allowed to SSH into worker instances"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
