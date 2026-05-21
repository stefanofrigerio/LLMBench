variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "g4dn.xlarge"  # GPU instance, use c5.2xlarge for CPU-only
}

variable "root_volume_size_gb" {
  description = "Root volume size in GB"
  type        = number
  default     = 100
}

variable "use_spot" {
  description = "Use spot instances for cost savings"
  type        = bool
  default     = true
}

variable "spot_max_price" {
  description = "Maximum price for spot instance (empty = on-demand price)"
  type        = string
  default     = ""
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key"
  type        = string
}

variable "allowed_ssh_cidrs" {
  description = "List of CIDR blocks allowed to SSH"
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
