#!/bin/bash
# Setup script for LLMBench with Poetry and venv

set -e

echo "🚀 Setting up LLMBench development environment"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "📍 Python version: $PYTHON_VERSION"

# Check Poetry
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    echo "✅ Poetry installed"
else
    echo "✅ Poetry found: $(poetry --version)"
fi

echo ""
echo "📦 Configuring Poetry to use in-project venv..."
poetry config virtualenvs.in-project true
poetry config virtualenvs.prefer-active-python true

echo ""
echo "🔧 Installing dependencies..."
poetry install --with dev

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment:"
echo "  source .venv/bin/activate"
echo ""
echo "Or use Poetry commands directly:"
echo "  poetry run pytest tests/"
echo "  poetry run llmbench --help"
echo ""
echo "Run tests with coverage:"
echo "  poetry run pytest tests/ --cov=src/llmbench --cov-report=term-missing"
