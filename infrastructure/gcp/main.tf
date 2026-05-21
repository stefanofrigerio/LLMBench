terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_compute_instance" "llmbench" {
  count        = var.worker_count
  name         = "llmbench-worker-${var.run_id}-${count.index}"
  machine_type = var.machine_type
  zone         = var.zone

  tags = ["llmbench", "benchmark-worker"]

  boot_disk {
    initialize_params {
      image = var.boot_image
      size  = var.boot_disk_size_gb
      type  = "pd-ssd"
    }
  }

  # GPU configuration (optional)
  dynamic "guest_accelerator" {
    for_each = var.gpu_type != "" ? [1] : []
    content {
      type  = var.gpu_type
      count = var.gpu_count
    }
  }

  # Enable GPU scheduling if GPU is present
  scheduling {
    on_host_maintenance = var.gpu_type != "" ? "TERMINATE" : "MIGRATE"
    automatic_restart   = false
    preemptible        = var.use_spot || var.use_preemptible
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP
    }
  }

  metadata = {
    ssh-keys           = "${var.ssh_user}:${file(var.ssh_public_key_path)}"
    user-data          = templatefile("${path.module}/../scripts/cloud-init.yaml", {
      models_to_pull = jsonencode(var.models_to_pull)
      controller_url = var.controller_url
      worker_id      = "worker-${count.index}"
    })
  }

  service_account {
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
    ]
  }

  labels = {
    purpose     = "llm-benchmark"
    run_id      = var.run_id
    managed_by  = "terraform"
  }

  lifecycle {
    ignore_changes = [
      metadata["ssh-keys"],
    ]
  }
}

resource "google_compute_firewall" "llmbench_ssh" {
  name    = "llmbench-allow-ssh-${var.run_id}"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.allowed_ssh_ips
  target_tags   = ["llmbench"]
}

output "worker_ips" {
  value       = google_compute_instance.llmbench[*].network_interface[0].access_config[0].nat_ip
  description = "Public IP addresses of all worker instances"
}

output "worker_names" {
  value       = google_compute_instance.llmbench[*].name
  description = "Names of all worker instances"
}

output "instance_ip" {
  value       = length(google_compute_instance.llmbench) > 0 ? google_compute_instance.llmbench[0].network_interface[0].access_config[0].nat_ip : null
  description = "Public IP address of first instance (backward compatibility)"
}

output "instance_name" {
  value       = length(google_compute_instance.llmbench) > 0 ? google_compute_instance.llmbench[0].name : null
  description = "Name of first instance (backward compatibility)"
}

output "instance_zone" {
  value       = length(google_compute_instance.llmbench) > 0 ? google_compute_instance.llmbench[0].zone : null
  description = "Zone of first instance (backward compatibility)"
}
