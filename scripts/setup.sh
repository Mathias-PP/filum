#!/usr/bin/env bash
# Setup script for new developers

set -e

echo "🚀 Filum Development Setup"
echo "=========================="

# Check prerequisites
echo ""
echo "📋 Checking prerequisites..."

check_command() {
    if command -v "$1" &> /dev/null; then
        VERSION=$($1 --version 2>&1 | head -1)
        echo "  ✅ $1: $VERSION"
    else
        echo "  ❌ $1: not found"
        MISSING=1
    fi
}

check_command python3
check_command git
check_command docker

# Node.js via nvm
if [ -d "$HOME/.nvm" ]; then
    source "$HOME/.nvm/nvm.sh"
    if command -v node &> /dev/null; then
        echo "  ✅ node: $(node --version)"
    else
        echo "  ⚠️  Node.js not installed (run: nvm install 22)"
    fi
    if command -v pnpm &> /dev/null; then
        echo "  ✅ pnpm: $(pnpm --version)"
    else
        echo "  ⚠️  pnpm not installed (run: npm install -g pnpm)"
    fi
else
    echo "  ⚠️  nvm not installed"
fi

# uv
if [ -f "$HOME/.local/bin/uv" ]; then
    echo "  ✅ uv: $(uv --version)"
else
    echo "  ⚠️  uv not installed (run: curl -LsSf https://astral.sh/uv/install.sh | sh)"
fi

# Install pre-commit hooks
echo ""
echo "🪝 Installing pre-commit hooks..."
if command -v pre-commit &> /dev/null; then
    pre-commit install --config .pre-commit-config.yaml
    echo "  ✅ Pre-commit hooks installed"
else
    echo "  ⚠️  pre-commit not installed (pip install pre-commit)"
fi

# Copy environment file
echo ""
echo "📝 Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ✅ .env file created"
    echo "  ⚠️  Please edit .env with your configuration"
else
    echo "  ✅ .env file exists"
fi

# Docker services
echo ""
echo "🐳 Starting Docker services..."
read -p "Start PostgreSQL with Docker? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    make docker-up || docker-compose up -d postgres
    echo "  ✅ PostgreSQL started"
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
read -p "Install backend dependencies? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    make backend-setup || (cd apps/backend && uv sync)
    echo "  ✅ Backend dependencies installed"
fi

read -p "Install frontend dependencies? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    make frontend-setup || (cd apps/frontend && pnpm install)
    echo "  ✅ Frontend dependencies installed"
fi

# Run migrations
echo ""
echo "🔄 Running initial migration..."
read -p "Run database migration? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    make migrate || (cd apps/backend && uv run alembic upgrade head)
    echo "  ✅ Migration complete"
fi

echo ""
echo "=========================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  make dev        # Start all services"
echo "  make test       # Run tests"
echo "  make seed       # Add demo data"
echo ""
echo "Happy coding! 🎉"
