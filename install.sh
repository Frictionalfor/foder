#!/usr/bin/env bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  FODER — Local AI Coding Agent Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────

if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Python $PYTHON_VERSION found, but 3.10+ is required."
    exit 1
fi

echo "✓ Python $PYTHON_VERSION detected"
echo ""

# ── Check Ollama ──────────────────────────────────────────────────────────────

if ! command -v ollama &> /dev/null; then
    echo "Ollama not found."
    echo ""
    echo "   Foder requires Ollama to run local LLMs."
    echo "   Install it from: https://ollama.com"
    echo ""
    read -p "   Continue without Ollama? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ Ollama detected"
fi

echo ""

# ── Install Foder ─────────────────────────────────────────────────────────────

echo "Installing foder..."
echo ""

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux — check for system package manager restrictions
    if python3 -m pip install --help &> /dev/null; then
        python3 -m pip install -e . --break-system-packages 2>/dev/null || python3 -m pip install -e .
    else
        echo "pip not available. Install python3-pip first."
        exit 1
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    python3 -m pip install -e .
else
    echo "Unknown OS: $OSTYPE"
    python3 -m pip install -e .
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Installation complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Run:  foder"
echo ""
echo "  If Ollama isn't running, start it first:"
echo "    ollama serve"
echo ""
echo "  Pull a model (if you haven't already):"
echo "    ollama pull qwen2.5-coder:7b"
echo ""
