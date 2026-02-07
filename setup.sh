#!/bin/bash
# Automated setup script for Vocabulary Learning App

set -e  # Exit on error

echo "🚀 Vocabulary Learning App - Setup Script"
echo "=========================================="
echo ""

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Conda is not installed. Please install Anaconda or Miniconda first."
    echo "   Download from: https://www.anaconda.com/download or https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "✅ Conda found"

# Navigate to project directory
PROJECT_DIR="/home/ethan/cool-vocabulary-learning-app-v2"
cd "$PROJECT_DIR"

# Create conda environment
ENV_NAME="vocab-app"
echo ""
echo "📦 Creating conda environment: $ENV_NAME"

if conda env list | grep -q "^$ENV_NAME "; then
    echo "⚠️  Environment '$ENV_NAME' already exists. Skipping creation."
else
    conda create -n "$ENV_NAME" python=3.10 -y
    echo "✅ Environment created"
fi

# Activate environment
echo ""
echo "🔧 Activating environment..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

# Install dependencies
echo ""
echo "📥 Installing dependencies from requirements.txt..."
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Check for .env file
echo ""
if [ -f ".env" ]; then
    echo "✅ .env file found"
else
    echo "⚠️  .env file not found. Creating template..."
    cat > .env << 'EOF'
# Required: OpenAI API Key (for sentence scoring)
OPENAI_API_KEY=your_openai_api_key_here

# Required: Session Secret Key
SESSION_SECRET_KEY=your_random_secret_key_here

# Optional: Google OAuth (if using Google login)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
EOF
    echo "📝 Created .env template. Please edit it with your actual credentials:"
    echo "   nano .env"
fi

# Initialize database (if needed)
echo ""
echo "🗄️  Checking database..."
if [ -f "vocab_system_v2.db" ]; then
    echo "✅ Database file found"
else
    echo "📦 Database will be created on first run"
fi

echo ""
echo "=========================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys: nano .env"
echo "2. Activate environment: conda activate $ENV_NAME"
echo "3. Run the app: python main.py"
echo "4. Open browser: http://127.0.0.1:8000"
echo ""
echo "Happy coding! 🎉"
