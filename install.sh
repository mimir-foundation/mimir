#!/usr/bin/env bash
set -euo pipefail

# ── Mimir Installer ─────────────────────────────────────────────────────────
#   curl -sSL https://raw.githubusercontent.com/mimir-foundation/mimir/main/install.sh | bash
# ─────────────────────────────────────────────────────────────────────────────

REPO="https://github.com/mimir-foundation/mimir.git"
INSTALL_DIR="${MIMIR_DIR:-$HOME/mimir}"

cyan='\033[0;36m'
green='\033[0;32m'
yellow='\033[1;33m'
red='\033[0;31m'
dim='\033[2m'
bold='\033[1m'
reset='\033[0m'

info()  { echo -e "  ${cyan}>${reset} $1"; }
ok()    { echo -e "  ${green}>${reset} $1"; }
warn()  { echo -e "  ${yellow}!${reset} $1"; }
fail()  { echo -e "  ${red}x${reset} $1"; exit 1; }

echo ""
echo -e "${bold}${cyan}  Mimir Installer${reset}"
echo -e "${dim}  Your AI-powered second brain${reset}"
echo ""

# ── Check prerequisites ─────────────────────────────────────────────────────

missing=""

if ! command -v git &>/dev/null; then
    missing="$missing git"
fi

if ! command -v docker &>/dev/null; then
    missing="$missing docker"
fi

if command -v docker &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
    if ! command -v docker-compose &>/dev/null; then
        missing="$missing docker-compose"
    fi
fi

if [ -n "$missing" ]; then
    fail "Missing required tools:${bold}$missing${reset}"
fi

ok "Prerequisites: git, docker, docker compose"

# ── Clone or update repo ────────────────────────────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing install at $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only -q
    ok "Repository updated"
else
    info "Cloning to $INSTALL_DIR"
    git clone -q "$REPO" "$INSTALL_DIR"
    ok "Repository cloned"
fi

cd "$INSTALL_DIR"

# ── Generate .env ────────────────────────────────────────────────────────────

if [ ! -f .env ]; then
    API_KEY=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    cp .env.example .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/^API_KEY=$/API_KEY=$API_KEY/" .env
    else
        sed -i "s/^API_KEY=$/API_KEY=$API_KEY/" .env
    fi
    ok "Generated .env with API key: ${bold}$API_KEY${reset}"
    echo -e "  ${dim}  Save this key — you'll need it during setup${reset}"
else
    ok "Existing .env found — keeping it"
fi

# ── Start containers ─────────────────────────────────────────────────────────

info "Starting containers (this may take a few minutes on first run)..."

if docker compose version &>/dev/null 2>&1; then
    docker compose up -d --build --quiet-pull 2>&1 | tail -1
else
    docker-compose up -d --build --quiet-pull 2>&1 | tail -1
fi

ok "Containers started"

# ── Pull Ollama models ───────────────────────────────────────────────────────

info "Pulling AI models (this may take a while)..."

# Wait for Ollama to be healthy
for i in $(seq 1 30); do
    if docker exec mimir-ollama ollama list &>/dev/null 2>&1; then
        break
    fi
    sleep 2
done

docker exec mimir-ollama ollama pull nomic-embed-text 2>&1 | tail -1
docker exec mimir-ollama ollama pull gemma4 2>&1 | tail -1
ok "Models ready: nomic-embed-text, gemma4"

# ── Install CLI ──────────────────────────────────────────────────────────────

VENV_DIR="$INSTALL_DIR/.venv"
CLI_OK=false

info "Installing mimir CLI..."

# Find python3
PYTHON=""
for py in python3 python; do
    if command -v "$py" &>/dev/null; then
        PYTHON="$py"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    warn "Python 3 not found"
elif ! "$PYTHON" -c "import sys; assert sys.version_info >= (3,12)" 2>/dev/null; then
    warn "Python 3.12+ required (found: $($PYTHON --version 2>&1))"
    PYTHON=""
fi

if [ -n "$PYTHON" ]; then
    # Ensure python3-venv is available
    if [ ! -d "$VENV_DIR" ]; then
        if ! "$PYTHON" -m venv "$VENV_DIR" 2>&1; then
            info "Installing python3-venv..."
            PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            if command -v apt-get &>/dev/null; then
                apt-get update -qq >/dev/null 2>&1
                apt-get install -y -qq "python${PY_VER}-venv" >/dev/null 2>&1 || \
                apt-get install -y -qq python3-venv >/dev/null 2>&1 || true
            fi
            if ! "$PYTHON" -m venv "$VENV_DIR" 2>&1; then
                warn "Cannot create venv — install python${PY_VER}-venv"
            fi
        fi
    fi

    if [ -d "$VENV_DIR" ]; then
        if "$VENV_DIR/bin/pip" install -q -e "$INSTALL_DIR/tui" 2>&1; then
            ok "CLI installed to $VENV_DIR"
            ln -sf "$VENV_DIR/bin/mimir" /usr/local/bin/mimir 2>/dev/null || \
            ln -sf "$VENV_DIR/bin/mimir" "$HOME/.local/bin/mimir" 2>/dev/null || true

            if command -v mimir &>/dev/null; then
                ok "mimir command is ready"
                CLI_OK=true
            else
                warn "Symlink failed — run directly:"
                echo -e "  ${dim}  $VENV_DIR/bin/mimir${reset}"
            fi
        else
            warn "pip install failed"
        fi
    fi
fi

if [ "$CLI_OK" = false ]; then
    echo ""
    warn "CLI not installed. You can install manually:"
    echo -e "  ${dim}  $PYTHON -m venv $VENV_DIR${reset}"
    echo -e "  ${dim}  $VENV_DIR/bin/pip install -e $INSTALL_DIR/tui${reset}"
    echo -e "  ${dim}  ln -s $VENV_DIR/bin/mimir /usr/local/bin/mimir${reset}"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${green}${bold}  Mimir is installed!${reset}"
echo ""
echo -e "  ${dim}Backend:${reset}   http://localhost:3080"
echo -e "  ${dim}Dashboard:${reset} http://localhost:3081"
echo -e "  ${dim}Data:${reset}      $INSTALL_DIR/data"
echo ""
echo -e "  Run ${bold}mimir${reset} to start the setup wizard."
echo ""
