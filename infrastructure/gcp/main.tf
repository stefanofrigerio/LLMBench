terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Authentication uses Application Default Credentials (ADC).
# Before running terraform, authenticate with:
#   gcloud auth login
#   gcloud auth application-default login
#   gcloud config set project YOUR_PROJECT_ID
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ---------------------------------------------------------------------------
# Worker instances
# ---------------------------------------------------------------------------

resource "google_compute_instance" "worker" {
  count        = var.worker_count
  name         = "llmbench-${var.run_id}-${count.index}"
  machine_type = var.machine_type
  zone         = var.zone

  tags = ["llmbench-worker"]

  boot_disk {
    initialize_params {
      # Ubuntu 24.04 LTS ships Python 3.12 — satisfies llmbench requirement >=3.11
      image = "ubuntu-os-cloud/ubuntu-2404-lts"
      size  = var.disk_size_gb
      type  = "pd-ssd"
    }
  }

  # GPU — only attached when gpu_type is set
  dynamic "guest_accelerator" {
    for_each = var.gpu_type != "" ? [1] : []
    content {
      type  = var.gpu_type
      count = var.gpu_count
    }
  }

  scheduling {
    # TERMINATE is required when a GPU is attached
    on_host_maintenance = var.gpu_type != "" ? "TERMINATE" : "MIGRATE"
    automatic_restart   = var.spot ? false : true
    preemptible         = var.spot
    provisioning_model  = var.spot ? "SPOT" : "STANDARD"
  }

  network_interface {
    network = "default"
    access_config {}  # ephemeral public IP
  }

  metadata = {
    user-data = templatefile("${path.module}/../scripts/cloud-init.yaml", {
      models_to_pull     = jsonencode(var.models_to_pull)
      controller_url     = var.controller_url
      worker_id          = "llmbench-worker-${count.index}"
      repo_url           = var.repo_url
      tailscale_auth_key = var.tailscale_auth_key
    })
  }

  service_account {
    scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
    ]
  }

  labels = {
    purpose    = "llm-benchmark"
    run-id     = replace(var.run_id, "_", "-")
    managed-by = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------

resource "google_compute_firewall" "allow_ssh" {
  # Name must be unique per project — scoped to this run
  name    = "llmbench-ssh-${replace(var.run_id, "_", "-")}"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.allowed_ssh_cidrs
  target_tags   = ["llmbench-worker"]
}
