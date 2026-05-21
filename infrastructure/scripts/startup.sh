#!/bin/bash
# GCP startup script (runs on every boot)

set -e

echo "=== LLMBench Startup Script ==="

# Install NVIDIA drivers if GPU is present
if lspci | grep -i nvidia > /dev/null 2>&1; then
    echo "NVIDIA GPU detected, installing drivers..."

    # Install NVIDIA driver
    if ! nvidia-smi > /dev/null 2>&1; then
        curl -fsSL https://nvidia.github.io/nvidia-docker/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-docker.gpg
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-docker.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-docker.list

        apt-get update
        apt-get install -y nvidia-driver-535

        echo "NVIDIA drivers installed, reboot may be required"
    else
        echo "NVIDIA drivers already installed"
    fi
fi

echo "=== Startup Complete ==="
