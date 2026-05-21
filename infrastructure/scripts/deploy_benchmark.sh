#!/bin/bash
# Script to deploy and run benchmark on remote instance

set -e

REMOTE_USER=${1:-ubuntu}
REMOTE_IP=${2}
SSH_KEY=${3}

if [ -z "$REMOTE_IP" ]; then
    echo "Usage: $0 [user] <remote_ip> <ssh_key>"
    exit 1
fi

echo "=== Deploying LLMBench to $REMOTE_USER@$REMOTE_IP ==="

# Wait for instance to be SSH-ready
echo "Waiting for SSH to be ready..."
for i in {1..60}; do
    if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_IP" "echo 'SSH ready'" 2>/dev/null; then
        echo "SSH connection established!"
        break
    fi
    echo "Waiting... ($i/60)"
    sleep 5
done

# Wait for cloud-init to complete
echo "Waiting for cloud-init setup to complete..."
ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_IP" << 'EOF'
while [ ! -f /opt/llmbench/.setup_complete ]; do
    echo "Waiting for setup to complete..."
    sleep 10
done
echo "Setup complete!"
EOF

# Copy LLMBench code
echo "Copying LLMBench code..."
rsync -avz -e "ssh -i $SSH_KEY" \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'venv' \
    --exclude 'results' \
    --exclude 'infrastructure' \
    ./ "$REMOTE_USER@$REMOTE_IP:/opt/llmbench/code/"

# Install dependencies
echo "Installing dependencies..."
ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_IP" << 'EOF'
cd /opt/llmbench/code
source /opt/llmbench/venv/bin/activate
pip install -e .
EOF

echo "=== Deployment Complete ==="
echo "To run benchmark:"
echo "  ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_IP"
echo "  cd /opt/llmbench/code"
echo "  source /opt/llmbench/venv/bin/activate"
echo "  python examples/run_benchmark.py"
