variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "machine_type" {
  description = "Machine type for the instance"
  type        = string
  default     = "n1-standard-4"
}

variable "gpu_type" {
  description = "GPU type (e.g., nvidia-tesla-t4). Leave empty for CPU-only"
  type        = string
  default     = ""
}

variable "gpu_count" {
  description = "Number of GPUs to attach"
  type        = number
  default     = 1
}

variable "boot_image" {
  description = "Boot disk image"
  type        = string
  default     = "ubuntu-os-cloud/ubuntu-2204-lts"
}

variable "boot_disk_size_gb" {
  description = "Boot disk size in GB"
  type        = number
  default     = 100
}

variable "use_preemptible" {
  description = "Use preemptible instance for cost savings"
  type        = bool
  default     = true
}

variable "ssh_user" {
  description = "SSH user for connecting to the instance"
  type        = string
  default     = "benchmarker"
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key"
  type        = string
}

variable "allowed_ssh_ips" {
  description = "List of IPs allowed to SSH"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Restrict this in production
}

variable "run_id" {
  description = "Unique identifier for this benchmark run"
  type        = string
}

variable "models_to_pull" {
  description = "List of Ollama models to pull"
  type        = list(string)
  default = [
    "deepseek-coder:6.7b",
    "qwen2.5-coder:7b",
    "llama3.1:8b"
  ]
}

variable "worker_count" {
  description = "Number of worker instances to provision"
  type        = number
  default     = 1
}

variable "controller_url" {
  description = "URL of the controller server (for worker registration)"
  type        = string
  default     = ""
}

variable "use_spot" {
  description = "Use spot instances (alias for use_preemptible)"
  type        = bool
  default     = true
}
