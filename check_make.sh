#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Checking Make Commands ==="

# Function to check command
check_command() {
    local cmd=$1
    local description=$2
    echo -n "Checking '$cmd': "
    
    if eval "$cmd" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $description"
        return 0
    else
        echo -e "${RED}✗${NC} $description"
        return 1
    fi
}

# Check basic commands
check_command "make help" "Help command works"
check_command "make clean" "Clean command works"

# Check Python environment
echo ""
echo "=== Python Environment Check ==="
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment exists"
    source .venv/bin/activate
    
    # Check required packages
    echo "Checking installed packages:"
    for pkg in fastapi uvicorn celery redis pydantic pytest ruff black mypy; do
        if python -c "import $pkg" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $pkg"
        else
            echo -e "  ${YELLOW}⚠${NC} $pkg not installed"
        fi
    done
else
    echo -e "${YELLOW}⚠${NC} Virtual environment not found. Run 'make install' first"
fi

# Check configuration
echo ""
echo "=== Configuration Check ==="
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
else
    echo -e "${YELLOW}⚠${NC} .env file not found. Run 'make init-env'"
fi

# Check Docker
echo ""
echo "=== Docker Check ==="
if command -v docker >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker is installed"
    if docker ps >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Docker daemon is running"
    else
        echo -e "${YELLOW}⚠${NC} Docker daemon is not running"
    fi
else
    echo -e "${RED}✗${NC} Docker is not installed"
fi

if command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker Compose is available"
else
    echo -e "${YELLOW}⚠${NC} Docker Compose is not available"
fi

# Check import
echo ""
echo "=== Python Import Check ==="
if python -c "import sys; sys.path.insert(0, '.'); from app.main import app" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} App imports successfully"
else
    echo -e "${RED}✗${NC} App import failed"
fi

echo ""
echo "=== Summary ==="
echo "To get started:"
echo "1. If virtual environment doesn't exist: make install"
echo "2. Activate virtual environment: source .venv/bin/activate"
echo "3. Initialize config: make init-env"
echo "4. Run dev server: make dev"
echo "5. Or start all services with Docker: make up"