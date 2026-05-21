output "worker_ips" {
  description = "Public IP addresses of all worker instances"
  value       = google_compute_instance.worker[*].network_interface[0].access_config[0].nat_ip
}

output "worker_names" {
  description = "Names of all worker instances"
  value       = google_compute_instance.worker[*].name
}

output "ssh_commands" {
  description = "SSH commands to connect to each worker"
  value = [
    for i, ip in google_compute_instance.worker[*].network_interface[0].access_config[0].nat_ip :
    "ssh ubuntu@${ip}"
  ]
}

output "run_id" {
  description = "Run ID used for this deployment"
  value       = var.run_id
}
