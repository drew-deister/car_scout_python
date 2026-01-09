#!/bin/bash

# Car Scout - Single Command Startup Script
# This script installs dependencies and starts backend, frontend, and ngrok

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}🚗 Car Scout - Starting Application${NC}"
echo "=========================================="

# Detect Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ Error: Python not found. Please install Python 3.8 or higher.${NC}"
    exit 1
fi

# Detect pip command
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    echo -e "${RED}❌ Error: pip not found. Please install pip.${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Found Python: $PYTHON_VERSION"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found${NC}"
    echo "Creating .env from template..."
    cat > .env << EOF
PORT=5001
MONGODB_URI=mongodb://localhost:27017/test
OPENAI_API_KEY=your_openai_api_key_here
MTA_API_KEY=your_mobile_text_alerts_api_key_here
MTA_AUTO_REPLY_TEMPLATE_ID=
MTA_WEBHOOK_SECRET=your_secret_key_here
MTA_ALERT_EMAIL=
EOF
    echo -e "${YELLOW}⚠️  Please edit .env file with your actual credentials before continuing${NC}"
    echo "Press Enter to continue or Ctrl+C to exit..."
    read
fi

# Install/upgrade dependencies
echo ""
echo -e "${GREEN}📦 Installing dependencies...${NC}"
$PIP_CMD install --upgrade pip --quiet
$PIP_CMD install -r requirements.txt --quiet
echo -e "${GREEN}✓${NC} Dependencies installed"

# Check if ngrok is installed, install if not (macOS)
if ! command -v ngrok &> /dev/null; then
    echo -e "${YELLOW}⚠️  ngrok not found. Installing via Homebrew...${NC}"
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo -e "${RED}❌ Homebrew not found${NC}"
        echo "Please install Homebrew first: https://brew.sh"
        echo "Or install ngrok manually: https://ngrok.com/download"
        read -p "Continue without ngrok? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        USE_NGROK=false
    else
        echo "Installing ngrok via Homebrew..."
        brew install ngrok/ngrok/ngrok
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓${NC} ngrok installed successfully"
            USE_NGROK=true
        else
            echo -e "${RED}❌ Failed to install ngrok${NC}"
            echo "You can install manually from: https://ngrok.com/download"
            read -p "Continue without ngrok? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
            USE_NGROK=false
        fi
    fi
else
    USE_NGROK=true
    echo -e "${GREEN}✓${NC} ngrok found"
fi

# Get port from .env or use default
PORT=$(grep -E "^PORT=" .env 2>/dev/null | cut -d '=' -f2 || echo "5001")
PORT=${PORT:-5001}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    if [ "$USE_NGROK" = true ] && [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
    fi
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Start backend server
echo ""
echo -e "${GREEN}🚀 Starting backend server on port $PORT...${NC}"
$PYTHON_CMD server.py &
BACKEND_PID=$!
sleep 2

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Backend failed to start${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Backend running (PID: $BACKEND_PID)"

# Start frontend (Streamlit)
echo ""
echo -e "${GREEN}🎨 Starting frontend (Streamlit)...${NC}"
$PYTHON_CMD -m streamlit run app.py --server.headless=true > /tmp/car_scout_frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 4

# Check if frontend started successfully
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Frontend failed to start${NC}"
    echo "Check /tmp/car_scout_frontend.log for errors"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✓${NC} Frontend running (PID: $FRONTEND_PID)"

# Start ngrok if available
if [ "$USE_NGROK" = true ]; then
    echo ""
    echo -e "${GREEN}🌐 Starting ngrok tunnel...${NC}"
    ngrok http $PORT --log=stdout > /tmp/ngrok.log 2>&1 &
    NGROK_PID=$!
    sleep 3
    
    # Try to get ngrok URL
    sleep 2
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
    
    if [ ! -z "$NGROK_URL" ]; then
        echo -e "${GREEN}✓${NC} ngrok running (PID: $NGROK_PID)"
        echo ""
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ Application is running!${NC}"
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo ""
        echo -e "📱 Frontend:     ${GREEN}http://localhost:8501${NC}"
        echo -e "🔧 Backend API:    ${GREEN}http://localhost:$PORT${NC}"
        echo -e "🌐 ngrok URL:    ${GREEN}$NGROK_URL${NC}"
        echo -e "📡 Webhook URL:  ${GREEN}$NGROK_URL/api/webhook/sms${NC}"
        echo -e "📊 ngrok UI:     ${GREEN}http://localhost:4040${NC}"
        echo ""
        echo -e "${YELLOW}⚠️  Configure Mobile Text Alerts webhook to:${NC}"
        echo -e "   ${GREEN}$NGROK_URL/api/webhook/sms${NC}"
    else
        echo -e "${YELLOW}⚠️  ngrok started but URL not available yet${NC}"
        echo -e "   Check http://localhost:4040 for the URL"
    fi
else
    echo ""
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ Application is running!${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "📱 Frontend:  ${GREEN}http://localhost:8501${NC}"
    echo -e "🔧 Backend:   ${GREEN}http://localhost:$PORT${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Note: ngrok is not running. Webhooks will not work.${NC}"
fi

echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Wait for all background processes
wait

