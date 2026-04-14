#!/usr/bin/env bash
set -euo pipefail

# ── Mimir Installer ─────────────────────────────────────────────────────────
#   bash <(curl -sSL https://raw.githubusercontent.com/mimir-foundation/mimir/main/install.sh)

# When piped via curl, stdin is the script itself. Reopen /dev/tty for user input.
exec 3</dev/tty 2>/dev/null || true
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

info "Pulling latest images..."

if docker compose version &>/dev/null 2>&1; then
    docker compose pull -q
    docker compose up -d --build 2>&1 | tail -1
else
    docker-compose pull -q
    docker-compose up -d --build 2>&1 | tail -1
fi

ok "Containers started"

# ── Ollama models ────────────────────────────────────────────────────────────

# Pull a model with live progress display
pull_model() {
    local model="$1"
    # Run pull and show output directly — ollama already renders progress
    # Use script -q to preserve carriage returns from docker exec
    docker exec mimir-ollama ollama pull "$model" || {
        warn "Failed to pull $model"
        return 1
    }
}

info "Waiting for Ollama..."
for i in $(seq 1 30); do
    if docker exec mimir-ollama ollama list &>/dev/null 2>&1; then
        break
    fi
    sleep 2
done

if ! docker exec mimir-ollama ollama list &>/dev/null 2>&1; then
    fail "Ollama container is not responding"
fi

# Show what's already installed
echo ""
echo -e "  ${bold}Installed models:${reset}"
installed=$(docker exec mimir-ollama ollama list 2>/dev/null | tail -n +2)
if [ -n "$installed" ]; then
    echo "$installed" | while IFS= read -r line; do
        name=$(echo "$line" | awk '{print $1}')
        size=$(echo "$line" | awk '{print $3, $4}')
        echo -e "    ${green}>${reset} $name ${dim}($size)${reset}"
    done
else
    echo -e "    ${dim}(none)${reset}"
fi

# Check if embedding model is present
has_embed=false
if docker exec mimir-ollama ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
    has_embed=true
fi

# Check which LLM models are present
has_llm=""
for m in gemma4 gemma4:e4b gemma4:e2b gemma4:26b gemma4:31b; do
    if docker exec mimir-ollama ollama list 2>/dev/null | grep -q "^${m}"; then
        has_llm="$m"
        break
    fi
done

# ── Embedding model ──
echo ""
if [ "$has_embed" = true ]; then
    ok "Embedding model (nomic-embed-text) already installed"
else
    info "Pulling embedding model: nomic-embed-text"
    pull_model "nomic-embed-text"
    ok "nomic-embed-text ready"
fi

# ── LLM model selection ──
echo ""
if [ -n "$has_llm" ]; then
    echo -e "  ${green}>${reset} LLM model found: ${bold}$has_llm${reset}"
    echo ""
    echo -e "  ${dim}You can keep this or pick a different Gemma 4 variant.${reset}"
else
    echo -e "  ${dim}No LLM model found. Pick a Gemma 4 variant to download.${reset}"
fi

echo ""
echo -e "  ${bold}Available Gemma 4 models:${reset}"
echo -e "    ${bold}1)${reset} gemma4        ${dim}— 9.6 GB, default balanced (e4b)${reset}"
echo -e "    ${bold}2)${reset} gemma4:e2b    ${dim}— 7.2 GB, smallest, fast${reset}"
echo -e "    ${bold}3)${reset} gemma4:26b    ${dim}— 18 GB, MoE, high quality${reset}"
echo -e "    ${bold}4)${reset} gemma4:31b    ${dim}— 20 GB, dense, best quality${reset}"
if [ -n "$has_llm" ]; then
    echo -e "    ${bold}s)${reset} skip          ${dim}— keep ${has_llm}${reset}"
fi
echo ""

while true; do
    if [ -n "$has_llm" ]; then
        printf "  Pick a model [1-4, s to skip]: "
    else
        printf "  Pick a model [1-4]: "
    fi
    read -r choice <&3 2>/dev/null || read -r choice
    case "$choice" in
        1) LLM_MODEL="gemma4"; break ;;
        2) LLM_MODEL="gemma4:e2b"; break ;;
        3) LLM_MODEL="gemma4:26b"; break ;;
        4) LLM_MODEL="gemma4:31b"; break ;;
        s|S)
            if [ -n "$has_llm" ]; then
                LLM_MODEL=""; break
            fi
            ;;
        "") LLM_MODEL="gemma4"; break ;;
        *) echo -e "  ${dim}Invalid choice${reset}" ;;
    esac
done

if [ -n "$LLM_MODEL" ]; then
    echo ""
    info "Pulling $LLM_MODEL..."
    pull_model "$LLM_MODEL"
    ok "$LLM_MODEL ready"

    # Update .env with chosen model
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/^LLM_MODEL=.*/LLM_MODEL=$LLM_MODEL/" .env
    else
        sed -i "s/^LLM_MODEL=.*/LLM_MODEL=$LLM_MODEL/" .env
    fi

    # Restart backend so it picks up the new model
    info "Restarting backend with $LLM_MODEL..."
    if docker compose version &>/dev/null 2>&1; then
        docker compose up -d mimir-backend 2>&1 | tail -1
    else
        docker-compose up -d mimir-backend 2>&1 | tail -1
    fi
    ok "Backend restarted"
else
    ok "Keeping $has_llm"
fi

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
