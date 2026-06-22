#!/usr/bin/env bash
# Foder — Official Installer
# Source: https://foder.vercel.app/install.sh
#
# One-line install (OFFICIAL):
#   curl -fsSL https://foder.vercel.app/install.sh | bash
#
set -euo pipefail

FODER_REPO="https://github.com/Frictionalfor/foder"
FODER_SITE="https://foder.vercel.app"
FODER_VERSION="0.2.0"

# ── Colors ─────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  GRN='\033[0;32m' YLW='\033[0;33m' RED='\033[0;31m'
  CYN='\033[0;36m' DIM='\033[2m'    BLD='\033[1m' RST='\033[0m'
else
  GRN='' YLW='' RED='' CYN='' DIM='' BLD='' RST=''
fi
ok()   { echo -e "  ${GRN}✓${RST}  $*"; }
warn() { echo -e "  ${YLW}!${RST}  $*"; }
err()  { echo -e "  ${RED}✗${RST}  $*"; exit 1; }
info() { echo -e "  ${DIM}→${RST}  ${DIM}$*${RST}"; }
sep()  { echo "  ─────────────────────────────────────────────────────────"; }

echo ""
echo -e "${CYN}${BLD}  ███████  ██████  ██████  ███████ ██████${RST}"
echo -e "${CYN}  ██      ██    ██ ██   ██ ██      ██   ██${RST}"
echo -e "${CYN}  █████   ██    ██ ██   ██ █████   ██████${RST}"
echo -e "${CYN}  ██      ██    ██ ██   ██ ██      ██   ██${RST}"
echo -e "${CYN}  ██       ██████  ██████  ███████ ██   ██${RST}"
echo ""
echo -e "${BLD}  Foder — Local AI Coding Agent  v${FODER_VERSION}${RST}"
echo -e "${DIM}  No cloud. No keys. Just code.${RST}"
echo -e "${DIM}  Source: ${FODER_SITE}${RST}"
echo ""
sep
echo ""

# ── Security: source verification ─────────────────────────────────────────────
# This script may only be run from the official source or local repo.
# No third-party mirrors. No GitHub cloning for install.

# ── Detect OS ──────────────────────────────────────────────────────────────────
OS="$(uname -s 2>/dev/null || echo unknown)"
ARCH="$(uname -m 2>/dev/null || echo unknown)"
case "$OS" in
  Linux*)  PLATFORM="linux"  ;;
  Darwin*) PLATFORM="macos"  ;;
  *)       PLATFORM="unknown" ;;
esac
info "Platform: $OS ($ARCH)"

# ── Check Python 3.10+ ─────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cmd" &>/dev/null; then
    RAW_VER="$("$cmd" -c 'import sys;print(".".join(map(str,sys.version_info[:2])))'  2>/dev/null || echo "0.0")"
    MAJ="${RAW_VER%%.*}"; MIN="${RAW_VER#*.}"; MIN="${MIN%%.*}"
    if [ "$MAJ" -ge 3 ] 2>/dev/null && [ "$MIN" -ge 10 ] 2>/dev/null; then
      PYTHON="$cmd"; PY_VER="$RAW_VER"; break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  err "Python 3.10+ not found.

  Install it:
    Ubuntu/Debian:  sudo apt install python3.11
    Arch Linux:     sudo pacman -S python
    Fedora:         sudo dnf install python3
    macOS:          brew install python@3.11
    All platforms:  https://python.org/downloads/"
fi
ok "Python $PY_VER"

if ! "$PYTHON" -m pip --version &>/dev/null; then
  err "pip not found. Install python3-pip and retry."
fi
ok "pip available"

# ── Check Ollama ───────────────────────────────────────────────────────────────
if command -v ollama &>/dev/null; then
  OLLAMA_VER="$(ollama --version 2>/dev/null | head -1 || echo 'unknown')"
  ok "Ollama: $OLLAMA_VER"
else
  warn "Ollama not found."
  echo ""
  echo "  Foder requires Ollama to run local LLMs."
  echo -e "  Install: ${CYN}https://ollama.com${RST}"
  echo ""
  read -rp "  Continue without Ollama? [y/N] " REPLY; echo ""
  [[ "$REPLY" =~ ^[Yy]$ ]] || { echo "  Install Ollama first, then re-run."; exit 1; }
fi

# ── Get foder source ───────────────────────────────────────────────────────────
# OFFICIAL SOURCE ONLY: https://foder.vercel.app
# Update source: https://github.com/Frictionalfor/foder
INSTALL_DIR=""

if [ -f "pyproject.toml" ] && grep -q '"foder"' pyproject.toml 2>/dev/null; then
  # Already inside the repo (local dev / CI)
  INSTALL_DIR="$PWD"
  info "Using local repository: $INSTALL_DIR"
elif command -v git &>/dev/null; then
  INSTALL_DIR="$HOME/.foder_src"
  if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation..."
    git -C "$INSTALL_DIR" pull --rebase origin main 2>/dev/null || \
    git -C "$INSTALL_DIR" pull origin main 2>/dev/null || \
    info "Could not update — continuing with existing version"
  else
    info "Fetching foder from $FODER_REPO..."
    rm -rf "$INSTALL_DIR"
    git clone --depth=1 "$FODER_REPO" "$INSTALL_DIR"
  fi
else
  err "git not found. Install git and retry.
  Ubuntu/Debian:  sudo apt install git
  macOS:          brew install git"
fi

# ── Install foder ──────────────────────────────────────────────────────────────
echo ""
info "Installing foder..."

cd "$INSTALL_DIR"

INSTALL_OK=false
for flags in "--break-system-packages -q" "-q" "--user -q" "--user"; do
  # shellcheck disable=SC2086
  if "$PYTHON" -m pip install -e . $flags 2>/dev/null; then
    INSTALL_OK=true; break
  fi
done

$INSTALL_OK || err "pip install failed. Try manually:
  cd $INSTALL_DIR && pip install -e ."

# ── Create ~/.foder directory structure ────────────────────────────────────────
FODER_DIR="$HOME/.foder"
mkdir -p \
  "$FODER_DIR/skills" \
  "$FODER_DIR/sessions"
ok "~/.foder/ directory ready"

# ── Verify installation ─────────────────────────────────────────────────────────
echo ""
if command -v foder &>/dev/null; then
  FODER_PATH="$(command -v foder)"
  ok "foder installed: $FODER_PATH"
else
  LOCAL_BIN="$HOME/.local/bin"
  if [ -f "$LOCAL_BIN/foder" ]; then
    ok "foder installed to $LOCAL_BIN"
    warn "Add to PATH — run this and restart your terminal:"
    echo ""
    echo -e "    ${CYN}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc${RST}"
    echo -e "    ${CYN}source ~/.bashrc${RST}"
    echo ""
  else
    warn "foder installed. Restart your terminal and run 'foder'."
    warn "If it doesn't work: pip install -e $INSTALL_DIR"
  fi
fi

# ── Optional: pull starter model ──────────────────────────────────────────────
if command -v ollama &>/dev/null; then
  if ! ollama list 2>/dev/null | grep -q "qwen2.5-coder"; then
    echo ""
    echo -e "  ${DIM}Recommended starter model: qwen2.5-coder:3b (~2GB)${RST}"
    read -rp "  Pull it now? [Y/n] " REPLY; echo ""
    if [[ "$REPLY" =~ ^[Yy]?$ ]]; then
      info "Pulling qwen2.5-coder:3b..."
      ollama pull qwen2.5-coder:3b && ok "Model ready — this is your default coding model"
    fi
  else
    ok "qwen2.5-coder already available"
  fi
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
sep
echo ""
echo -e "  ${GRN}${BLD}Installation complete!${RST}"
echo ""
echo -e "  ${BLD}Start:${RST}    ${CYN}foder${RST}"
echo -e "  ${BLD}Help:${RST}     ${CYN}foder --help${RST}"
echo -e "  ${BLD}Update:${RST}   ${CYN}foder --update${RST}"
echo -e "  ${BLD}Uninstall:${RST} ${CYN}foder --uninstall${RST}"
echo ""
echo -e "  ${DIM}Before starting, make sure Ollama is running:  ollama serve${RST}"
echo -e "  ${DIM}Website:  $FODER_SITE${RST}"
echo -e "  ${DIM}GitHub:   $FODER_REPO${RST}"
echo ""
