terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "llmbench" {
  name        = "llmbench-${var.run_id}"
  description = "Security group for LLMBench runner"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.allowed_ssh_cidrs
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name       = "llmbench-${var.run_id}"
    Purpose    = "llm-benchmark"
    RunId      = var.run_id
    ManagedBy  = "terraform"
  }
}

resource "aws_key_pair" "llmbench" {
  key_name   = "llmbench-${var.run_id}"
  public_key = file(var.ssh_public_key_path)

  tags = {
    Purpose   = "llm-benchmark"
    RunId     = var.run_id
    ManagedBy = "terraform"
  }
}

locals {
  actual_instance_type = var.machine_type != "" ? var.machine_type : var.instance_type
}

resource "aws_instance" "llmbench" {
  count         = var.worker_count
  ami           = data.aws_ami.ubuntu.id
  instance_type = local.actual_instance_type
  key_name      = aws_key_pair.llmbench.key_name

  vpc_security_group_ids = [aws_security_group.llmbench.id]

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/../scripts/cloud-init.yaml", {
    models_to_pull = jsonencode(var.models_to_pull)
    controller_url = var.controller_url
    worker_id      = "worker-${count.index}"
  })

  instance_market_options {
    market_type = var.use_spot ? "spot" : null

    dynamic "spot_options" {
      for_each = var.use_spot ? [1] : []
      content {
        max_price          = var.spot_max_price
        spot_instance_type = "one-time"
      }
    }
  }

  tags = {
    Name       = "llmbench-worker-${var.run_id}-${count.index}"
    Purpose    = "llm-benchmark"
    RunId      = var.run_id
    ManagedBy  = "terraform"
  }

  lifecycle {
    ignore_changes = [ami]
  }
}

output "worker_ips" {
  value       = aws_instance.llmbench[*].public_ip
  description = "Public IP addresses of all worker instances"
}

output "worker_ids" {
  value       = aws_instance.llmbench[*].id
  description = "IDs of all worker instances"
}

output "instance_ip" {
  value       = length(aws_instance.llmbench) > 0 ? aws_instance.llmbench[0].public_ip : null
  description = "Public IP address of first instance (backward compatibility)"
}

output "instance_id" {
  value       = length(aws_instance.llmbench) > 0 ? aws_instance.llmbench[0].id : null
  description = "ID of first instance (backward compatibility)"
}

output "instance_dns" {
  value       = length(aws_instance.llmbench) > 0 ? aws_instance.llmbench[0].public_dns : null
  description = "Public DNS of first instance (backward compatibility)"
}
