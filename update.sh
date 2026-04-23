#!/usr/bin/env bash
# Foder auto-updater
# Usage: bash update.sh
# Pulls latest from git and reinstalls

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Foder Updater"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check git ─────────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    echo "  [x] git not found. Install git first."
    exit 1
fi

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "  [x] Not a git repository: $REPO_DIR"
    echo "      Clone from: https://github.com/Frictionalfor/foder.git"
    exit 1
fi

# ── Get current version ───────────────────────────────────────────────────────
CURRENT=$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "  Current commit : $CURRENT"

# ── Fetch latest ──────────────────────────────────────────────────────────────
echo "  Checking for updates..."
git -C "$REPO_DIR" fetch origin --quiet

BRANCH=$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
LOCAL=$(git -C "$REPO_DIR" rev-parse HEAD)
REMOTE=$(git -C "$REPO_DIR" rev-parse "origin/$BRANCH" 2>/dev/null)

if [ -z "$REMOTE" ]; then
    echo "  [!] Cannot reach remote. Check your internet connection."
    exit 1
fi

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "  Already up to date."
    echo ""
    exit 0
fi

# ── Show what changed ─────────────────────────────────────────────────────────
echo ""
echo "  Updates available:"
git -C "$REPO_DIR" log --oneline "HEAD..origin/$BRANCH" 2>/dev/null
echo ""
# ── Pull ──────────────────────────────────────────────────────────────────────
echo "  Pulling latest..."
BRANCH=$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
echo "  Branch: $BRANCH"
git -C "$REPO_DIR" pull --rebase origin "$BRANCH" 2>/dev/null || \
git -C "$REPO_DIR" pull origin "$BRANCH" 2>/dev/null || {
    echo "  [x] Pull failed. Try manually: git pull"
    exit 1
}

# ── Reinstall ─────────────────────────────────────────────────────────────────
echo "  Reinstalling..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    pip install -e "$REPO_DIR" --break-system-packages -q 2>/dev/null || \
    pip install -e "$REPO_DIR" -q
else
    pip install -e "$REPO_DIR" -q
fi

NEW=$(git -C "$REPO_DIR" rev-parse --short HEAD)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Updated: $CURRENT → $NEW"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Run: foder"
echo ""
