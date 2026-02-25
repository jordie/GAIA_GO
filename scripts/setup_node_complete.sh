#!/bin/bash
################################################################################
# Complete Node Setup Script for Architect Dashboard
#
# Sets up a distributed node with:
# - Ollama (local LLM runtime)
# - Gemini CLI (Google AI)
# - Claude Code integration
# - Node agent (metrics reporting)
# - Optional: OpenWebUI, AnythingLLM, n8n
#
# Usage:
#   chmod +x setup_node_complete.sh
#   ./setup_node_complete.sh [OPTIONS]
#
# Options:
#   --dashboard-url URL      Architect dashboard URL (default: http://localhost:8080)
#   --node-name NAME         Node name (default: detected hostname)
#   --node-port PORT         Node agent port (default: 9000)
#   --ollama-port PORT       Ollama port (default: 11434)
#   --with-webui             Install OpenWebUI (default: no)
#   --with-anythingllm       Install AnythingLLM (default: no)
#   --with-n8n               Install n8n workflow automation (default: no)
#   --skip-docker            Skip Docker installation
#   --dry-run                Show what would be installed (don't run)
#
# Example:
#   ./setup_node_complete.sh \
#     --dashboard-url http://192.168.1.100:8080 \
#     --node-name pink-laptop \
#     --with-webui
#
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DASHBOARD_URL="http://localhost:8080"
NODE_NAME=$(hostname -s 2>/dev/null || echo "node-$(date +%s)")
NODE_PORT=9000
OLLAMA_PORT=11434
INSTALL_WEBUI=false
INSTALL_ANYTHINGLLM=false
INSTALL_N8N=false
SKIP_DOCKER=false
DRY_RUN=false

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    DISTRO=$(lsb_release -si 2>/dev/null || echo "unknown")
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dashboard-url)
            DASHBOARD_URL="$2"
            shift 2
            ;;
        --node-name)
            NODE_NAME="$2"
            shift 2
            ;;
        --node-port)
            NODE_PORT="$2"
            shift 2
            ;;
        --ollama-port)
            OLLAMA_PORT="$2"
            shift 2
            ;;
        --with-webui)
            INSTALL_WEBUI=true
            shift
            ;;
        --with-anythingllm)
            INSTALL_ANYTHINGLLM=true
            shift
            ;;
        --with-n8n)
            INSTALL_N8N=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Utility functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] $@"
    else
        "$@"
    fi
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Header
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Architect Dashboard - Complete Node Setup Script       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

log_info "OS detected: $OS"
log_info "Node name: $NODE_NAME"
log_info "Dashboard URL: $DASHBOARD_URL"
log_info "Dry run mode: $DRY_RUN"
echo ""

################################################################################
# 1. System Dependencies
################################################################################
log_info "Checking system dependencies..."

install_deps() {
    if [ "$OS" = "macos" ]; then
        if ! check_command brew; then
            log_info "Installing Homebrew..."
            run_cmd /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi

        log_info "Installing dependencies via Homebrew..."
        run_cmd brew install \
            python@3.11 \
            git \
            curl \
            wget \
            jq \
            node \
            docker

    elif [ "$OS" = "linux" ]; then
        if check_command apt-get; then
            log_info "Updating package manager..."
            run_cmd sudo apt-get update -qq

            log_info "Installing dependencies via apt..."
            run_cmd sudo apt-get install -y \
                python3 \
                python3-pip \
                python3-venv \
                git \
                curl \
                wget \
                jq \
                nodejs \
                npm
        elif check_command yum; then
            log_info "Installing dependencies via yum..."
            run_cmd sudo yum install -y \
                python3 \
                python3-pip \
                git \
                curl \
                wget \
                jq \
                nodejs \
                npm
        fi
    fi
}

run_cmd install_deps
log_success "System dependencies ready"
echo ""

################################################################################
# 2. Ollama Setup
################################################################################
log_info "Setting up Ollama (local LLM runtime)..."

if check_command ollama; then
    log_warn "Ollama already installed"
else
    log_info "Installing Ollama..."
    if [ "$OS" = "macos" ]; then
        run_cmd curl -fsSL https://ollama.ai/install.sh | bash
    elif [ "$OS" = "linux" ]; then
        run_cmd curl -fsSL https://ollama.ai/install.sh | bash
    fi
fi

# Create ollama config
log_info "Configuring Ollama..."
mkdir -p "$HOME/.ollama"

if [ "$DRY_RUN" = false ]; then
    cat > "$HOME/.ollama/config.json" << 'EOF'
{
  "models_dir": "~/.ollama/models",
  "num_parallel": 2,
  "max_queue_size": 1000,
  "request_timeout": 300,
  "enable_metrics": true
}
EOF
fi

log_success "Ollama configured (port: $OLLAMA_PORT)"
echo ""

################################################################################
# 3. Gemini CLI Setup
################################################################################
log_info "Setting up Gemini CLI..."

if check_command gemini; then
    log_warn "Gemini CLI already installed"
else
    log_info "Installing Gemini CLI..."
    run_cmd npm install -g @google/generative-ai

    # Create wrapper script
    log_info "Creating gemini wrapper script..."
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$HOME/.local/bin"
        cat > "$HOME/.local/bin/gemini" << 'EOF'
#!/bin/bash
# Gemini CLI wrapper for architect integration
node -e "
const { GoogleGenerativeAI } = require('@google/generative-ai');
(async () => {
  const apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    console.error('GOOGLE_API_KEY environment variable not set');
    process.exit(1);
  }
  const client = new GoogleGenerativeAI(apiKey);
  const model = client.getGenerativeModel({ model: 'gemini-pro' });
  const result = await model.generateContent(process.argv.slice(1).join(' '));
  console.log(result.response.text());
})();
" "$@"
EOF
        chmod +x "$HOME/.local/bin/gemini"
    fi
fi

log_success "Gemini CLI configured"
echo ""

################################################################################
# 4. Docker Setup (for optional services)
################################################################################
if [ "$SKIP_DOCKER" = false ]; then
    log_info "Setting up Docker..."

    if ! check_command docker; then
        log_info "Installing Docker..."
        if [ "$OS" = "macos" ]; then
            run_cmd brew install --cask docker
        elif [ "$OS" = "linux" ]; then
            run_cmd curl -fsSL https://get.docker.com | bash
            if [ "$DRY_RUN" = false ]; then
                sudo usermod -aG docker "$USER"
            fi
        fi
    fi

    log_success "Docker ready"
fi
echo ""

################################################################################
# 5. Python Environment & Node Agent
################################################################################
log_info "Setting up Python environment..."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$DRY_RUN" = false ]; then
    # Create venv
    if [ ! -d "$PROJECT_DIR/venv" ]; then
        python3 -m venv "$PROJECT_DIR/venv"
    fi

    # Activate venv
    source "$PROJECT_DIR/venv/bin/activate"

    # Install requirements
    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        pip install -q -r "$PROJECT_DIR/requirements.txt"
    fi

    # Install node agent requirements
    if [ -f "$PROJECT_DIR/distributed/requirements.txt" ]; then
        pip install -q -r "$PROJECT_DIR/distributed/requirements.txt"
    fi
fi

log_success "Python environment ready"
echo ""

################################################################################
# 6. Node Agent Configuration
################################################################################
log_info "Configuring node agent..."

if [ "$DRY_RUN" = false ]; then
    cat > "$PROJECT_DIR/node_config.json" << EOF
{
  "node_name": "$NODE_NAME",
  "node_port": $NODE_PORT,
  "dashboard_url": "$DASHBOARD_URL",
  "ollama_endpoint": "http://localhost:$OLLAMA_PORT",
  "report_interval": 30,
  "enable_metrics": true,
  "metrics": {
    "cpu": true,
    "memory": true,
    "disk": true,
    "network": true,
    "processes": true
  },
  "services": {
    "ollama": {
      "port": $OLLAMA_PORT,
      "health_check": "http://localhost:$OLLAMA_PORT/api/tags"
    },
    "gemini": {
      "enabled": true,
      "requires_api_key": true
    }
  }
}
EOF
fi

log_success "Node agent configured"
echo ""

################################################################################
# 7. Optional Services
################################################################################

if [ "$INSTALL_WEBUI" = true ]; then
    log_info "Installing OpenWebUI (ChatGPT-like interface)..."
    if [ "$DRY_RUN" = false ] && ! check_command docker; then
        log_warn "Docker required for OpenWebUI but not installed"
    elif [ "$DRY_RUN" = false ]; then
        docker pull ghcr.io/open-webui/open-webui:latest
        cat > "$PROJECT_DIR/docker-compose-webui.yml" << 'EOF'
version: '3.8'
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:latest
    ports:
      - "3000:8080"
    environment:
      - OLLAMA_API_BASE_URL=http://ollama:11434/api
    volumes:
      - open-webui-data:/app/backend/data
    networks:
      - architect

volumes:
  open-webui-data:

networks:
  architect:
    driver: bridge
EOF
        log_success "OpenWebUI configured (port 3000)"
    fi
fi

if [ "$INSTALL_ANYTHINGLLM" = true ]; then
    log_info "Installing AnythingLLM (RAG system)..."
    if [ "$DRY_RUN" = false ] && ! check_command docker; then
        log_warn "Docker required for AnythingLLM but not installed"
    elif [ "$DRY_RUN" = false ]; then
        docker pull mintplexlabs/anythingllm:latest
        cat > "$PROJECT_DIR/docker-compose-anythingllm.yml" << 'EOF'
version: '3.8'
services:
  anythingllm:
    image: mintplexlabs/anythingllm:latest
    ports:
      - "3001:3001"
    environment:
      - LLM_PROVIDER=ollama
      - OLLAMA_BASE_PATH=http://ollama:11434
    volumes:
      - anythingllm-data:/app/server/storage
    networks:
      - architect

volumes:
  anythingllm-data:

networks:
  architect:
    driver: bridge
EOF
        log_success "AnythingLLM configured (port 3001)"
    fi
fi

if [ "$INSTALL_N8N" = true ]; then
    log_info "Installing n8n (workflow automation)..."
    if [ "$DRY_RUN" = false ] && ! check_command docker; then
        log_warn "Docker required for n8n but not installed"
    elif [ "$DRY_RUN" = false ]; then
        docker pull n8nio/n8n:latest
        cat > "$PROJECT_DIR/docker-compose-n8n.yml" << 'EOF'
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=architect
    volumes:
      - n8n-data:/home/node/.n8n
    networks:
      - architect

volumes:
  n8n-data:

networks:
  architect:
    driver: bridge
EOF
        log_success "n8n configured (port 5678)"
    fi
fi

echo ""

################################################################################
# 8. Environment Configuration
################################################################################
log_info "Setting up environment variables..."

if [ "$DRY_RUN" = false ]; then
    ENV_FILE="$HOME/.architect_node.env"

    cat > "$ENV_FILE" << EOF
# Architect Node Environment
export NODE_NAME=$NODE_NAME
export NODE_PORT=$NODE_PORT
export DASHBOARD_URL=$DASHBOARD_URL
export OLLAMA_ENDPOINT=http://localhost:$OLLAMA_PORT

# API Keys (set these manually)
export GOOGLE_API_KEY=your_api_key_here
export ANTHROPIC_API_KEY=your_api_key_here
export OPENAI_API_KEY=your_api_key_here

# LLM Provider Configuration
export LLM_DEFAULT_PROVIDER=ollama
export LLM_FAILOVER_ENABLED=true

# Node Agent
export NODE_AGENT_PORT=$NODE_PORT
export REPORT_METRICS=true
export METRICS_INTERVAL=30

# Optional services
export WEBUI_ENABLED=$INSTALL_WEBUI
export ANYTHINGLLM_ENABLED=$INSTALL_ANYTHINGLLM
export N8N_ENABLED=$INSTALL_N8N
EOF

    echo "source $ENV_FILE" >> "$HOME/.bashrc"
    echo "source $ENV_FILE" >> "$HOME/.zshrc" 2>/dev/null || true

    log_success "Environment file created: $ENV_FILE"
fi

echo ""

################################################################################
# 9. Startup Scripts
################################################################################
log_info "Creating startup scripts..."

if [ "$DRY_RUN" = false ]; then
    SCRIPTS_DIR="$PROJECT_DIR/scripts"
    mkdir -p "$SCRIPTS_DIR"

    # Ollama startup
    cat > "$SCRIPTS_DIR/start_ollama.sh" << EOF
#!/bin/bash
source "$HOME/.architect_node.env"
ollama serve --port \$OLLAMA_ENDPOINT
EOF
    chmod +x "$SCRIPTS_DIR/start_ollama.sh"

    # Node agent startup
    cat > "$SCRIPTS_DIR/start_node_agent.sh" << EOF
#!/bin/bash
source "$HOME/.architect_node.env"
cd "$PROJECT_DIR"
python3 distributed/node_agent.py \\
  --name "\$NODE_NAME" \\
  --port \$NODE_PORT \\
  --dashboard "\$DASHBOARD_URL" \\
  --daemon
EOF
    chmod +x "$SCRIPTS_DIR/start_node_agent.sh"

    # All services startup
    cat > "$SCRIPTS_DIR/start_all_services.sh" << EOF
#!/bin/bash
set -e

source "$HOME/.architect_node.env"

echo "Starting Ollama..."
nohup "$SCRIPTS_DIR/start_ollama.sh" > /tmp/ollama.log 2>&1 &

sleep 2

echo "Starting node agent..."
"$SCRIPTS_DIR/start_node_agent.sh"

if [ "\$WEBUI_ENABLED" = "true" ]; then
    echo "Starting OpenWebUI..."
    docker-compose -f "$PROJECT_DIR/docker-compose-webui.yml" up -d
fi

if [ "\$ANYTHINGLLM_ENABLED" = "true" ]; then
    echo "Starting AnythingLLM..."
    docker-compose -f "$PROJECT_DIR/docker-compose-anythingllm.yml" up -d
fi

if [ "\$N8N_ENABLED" = "true" ]; then
    echo "Starting n8n..."
    docker-compose -f "$PROJECT_DIR/docker-compose-n8n.yml" up -d
fi

echo "All services started!"
echo "Dashboard: \$DASHBOARD_URL"
echo "Ollama: http://localhost:\$OLLAMA_ENDPOINT"
EOF
    chmod +x "$SCRIPTS_DIR/start_all_services.sh"

    log_success "Startup scripts created in $SCRIPTS_DIR"
fi

echo ""

################################################################################
# 10. Node Registration
################################################################################
log_info "Registering node with dashboard..."

if [ "$DRY_RUN" = false ]; then
    HOSTNAME=$(hostname -f 2>/dev/null || hostname)
    IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")

    REGISTER_PAYLOAD=$(cat <<EOF
{
  "name": "$NODE_NAME",
  "hostname": "$HOSTNAME",
  "address": "$IP",
  "port": $NODE_PORT,
  "status": "online",
  "capabilities": [
    "ollama",
    "gemini",
    "task_execution",
    "metrics_reporting"
  ],
  "config": {
    "ollama_port": $OLLAMA_PORT,
    "dashboard_url": "$DASHBOARD_URL"
  }
}
EOF
    )

    log_info "Sending registration to $DASHBOARD_URL/api/nodes"
    if check_command curl; then
        RESPONSE=$(curl -s -X POST \
            "$DASHBOARD_URL/api/nodes" \
            -H "Content-Type: application/json" \
            -d "$REGISTER_PAYLOAD" || echo "registration_failed")

        if [[ $RESPONSE == *"error"* ]] || [[ $RESPONSE == "registration_failed" ]]; then
            log_warn "Node registration pending dashboard availability"
        else
            log_success "Node registered successfully"
        fi
    fi
fi

echo ""

################################################################################
# 11. Health Check
################################################################################
log_info "Running health checks..."

health_ok=true

# Check Python
if check_command python3; then
    log_success "Python installed: $(python3 --version)"
else
    log_error "Python not found"
    health_ok=false
fi

# Check pip
if check_command pip3; then
    log_success "pip installed"
else
    log_error "pip not found"
    health_ok=false
fi

# Check Node.js
if check_command node; then
    log_success "Node.js installed: $(node --version)"
else
    log_error "Node.js not found"
    health_ok=false
fi

# Check curl
if check_command curl; then
    log_success "curl installed"
else
    log_error "curl not found"
    health_ok=false
fi

echo ""

################################################################################
# 12. Summary
################################################################################
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Setup Complete - Next Steps                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

cat << EOF

1. Configure API Keys:
   Edit: $HOME/.architect_node.env

   Set these values:
   - GOOGLE_API_KEY (for Gemini)
   - ANTHROPIC_API_KEY (for Claude)
   - OPENAI_API_KEY (optional)

2. Start Services:
   $PROJECT_DIR/scripts/start_all_services.sh

3. Verify Ollama:
   curl http://localhost:$OLLAMA_PORT/api/tags

4. Pull Models (optional):
   ollama pull mistral
   ollama pull codellama
   ollama pull neural-chat

5. Access Dashboard:
   $DASHBOARD_URL

   Node: $NODE_NAME
   Port: $NODE_PORT
   Ollama: http://localhost:$OLLAMA_PORT

EOF

if [ "$INSTALL_WEBUI" = true ]; then
    echo "6. OpenWebUI:"
    echo "   http://localhost:3000"
    echo ""
fi

if [ "$INSTALL_ANYTHINGLLM" = true ]; then
    echo "7. AnythingLLM:"
    echo "   http://localhost:3001"
    echo ""
fi

if [ "$INSTALL_N8N" = true ]; then
    echo "8. n8n Workflows:"
    echo "   http://localhost:5678"
    echo ""
fi

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY RUN: No changes were made${NC}"
fi

log_success "Setup script completed!"
