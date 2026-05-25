#!/bin/bash

# Cash Crew Setup Script
# This script sets up the development environment for Cash Crew

set -e  # Exit on error

echo "🚀 Cash Crew Setup Script"
echo "=========================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $python_version found"

# Check if we're in the right directory
if [ ! -f "backend/requirements.txt" ]; then
    echo "❌ Error: Please run this script from the cash-crew root directory"
    exit 1
fi

# Backend setup
echo ""
echo "📦 Setting up backend..."
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit backend/.env and add your API keys!"
else
    echo "✓ .env file already exists"
fi

cd ..

# Frontend setup (if frontend directory exists)
if [ -d "frontend" ]; then
    echo ""
    echo "📦 Setting up frontend..."
    cd frontend
    
    # Check if Node.js is installed
    if command -v node &> /dev/null; then
        node_version=$(node --version)
        echo "✓ Node.js $node_version found"
        
        # Install dependencies
        if [ ! -d "node_modules" ]; then
            echo "Installing Node.js dependencies..."
            npm install
            echo "✓ Dependencies installed"
        else
            echo "✓ Dependencies already installed"
        fi
        
        # Copy .env.local if it doesn't exist
        if [ ! -f ".env.local" ]; then
            if [ -f ".env.example" ]; then
                echo "Creating .env.local file from template..."
                cp .env.example .env.local
                echo "✓ .env.local file created"
            fi
        else
            echo "✓ .env.local file already exists"
        fi
    else
        echo "⚠️  Node.js not found. Skipping frontend setup."
        echo "   Install Node.js from https://nodejs.org/"
    fi
    
    cd ..
fi

# Ollama setup check
echo ""
echo "🤖 Checking Ollama installation..."
if command -v ollama &> /dev/null; then
    echo "✓ Ollama is installed"
    echo ""
    echo "Checking for required models..."
    
    # Check for llama3
    if ollama list | grep -q "llama3"; then
        echo "✓ llama3 model found"
    else
        echo "⚠️  llama3 model not found"
        echo "   Run: ollama pull llama3"
    fi
    
    # Check for mixtral
    if ollama list | grep -q "mixtral"; then
        echo "✓ mixtral model found"
    else
        echo "⚠️  mixtral model not found"
        echo "   Run: ollama pull mixtral"
    fi
    
    # Check for mistral
    if ollama list | grep -q "mistral"; then
        echo "✓ mistral model found"
    else
        echo "⚠️  mistral model not found"
        echo "   Run: ollama pull mistral"
    fi
else
    echo "⚠️  Ollama not found (optional for offline demo)"
    echo "   Install from: https://ollama.ai/"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit backend/.env and add your API keys"
echo "2. Start the backend:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   uvicorn main:app --reload"
echo ""
echo "3. (Optional) Start the frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "4. Access the API at http://localhost:8000"
echo "   API docs at http://localhost:8000/docs"
echo ""
echo "Happy analyzing! 💰📊"
