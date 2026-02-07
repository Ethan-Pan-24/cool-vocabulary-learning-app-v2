#!/bin/bash
# Simple setup script using Python venv (no Conda required)

set -e
echo "🚀 Setting up Vocabulary Learning App (using Python venv)"
echo "=========================================="

cd /home/ethan/cool-vocabulary-learning-app-v2

# Check Python version
echo "✅ Checking Python..."
python3 --version

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate and install dependencies
echo ""
echo "📥 Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo ""
echo "To run the app:"
echo "  1. source venv/bin/activate"
echo "  2. python3 main.py"
echo ""
