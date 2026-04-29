#!/bin/bash
# Setup script for ADAG Phase 1

set -e

echo "========================================================================"
echo "  ADAG - AI-Driven Architecture Guardrail Setup"
echo "  Phase 1: Deletion Protection Checker"
echo "========================================================================"
echo ""

# Pull latest changes
echo "Pulling latest changes from GitHub..."
git pull || { echo "Warning: git pull failed, continuing with existing code"; }

# Check Python version
echo "Checking Python version..."
python3 --version || { echo "Error: Python 3 is required"; exit 1; }

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and configure your AWS credentials"
else
    echo ".env file already exists"
fi

# Create data directory for SQLite
mkdir -p data

echo ""
echo "========================================================================"
echo "✓ Setup complete!"
echo "========================================================================"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Configure your provider in .env:"
echo "   - GitHub Copilot: set LLM_PROVIDER=github-copilot and GITHUB_COPILOT_TOKEN"
echo "   - AWS Bedrock:    set LLM_PROVIDER=bedrock and AWS credentials"
echo "   - HuggingFace:   set LLM_PROVIDER=huggingface and HF_TOKEN"
echo "3. Run tests: pytest tests/ -v"
echo "4. Run the application: python main.py tests/fixtures/bad_terraform.tf"
echo ""
echo "For more information, see README.md"
echo ""
