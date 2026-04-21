# Foder — Windows Installer (PowerShell)
# Run with: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  FODER — Local AI Coding Agent Installer" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# ── Check Python ──────────────────────────────────────────────────────────────

$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $python = $cmd
        break
    }
}

if (-not $python) {
    Write-Host "  [X] Python not found. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}

$version = & $python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
Write-Host "  [+] Python $version detected" -ForegroundColor Green

# ── Check Ollama ──────────────────────────────────────────────────────────────

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "  [+] Ollama detected" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  [!] Ollama not found." -ForegroundColor Yellow
    Write-Host "      Foder requires Ollama to run local LLMs." -ForegroundColor Yellow
    Write-Host "      Install from: https://ollama.com" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "  Continue without Ollama? (y/N)"
    if ($continue -notmatch "^[Yy]$") {
        exit 1
    }
}

Write-Host ""

# ── Install Foder ─────────────────────────────────────────────────────────────

Write-Host "  Installing foder..." -ForegroundColor Cyan
Write-Host ""

try {
    & $python -m pip install -e . --quiet
} catch {
    Write-Host "  [X] Installation failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "  [+] Installation complete!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host "  Run:  foder" -ForegroundColor White
Write-Host ""
Write-Host "  If Ollama isn't running, start it first:" -ForegroundColor DarkGray
Write-Host "    ollama serve" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Pull a model (if you haven't already):" -ForegroundColor DarkGray
Write-Host "    ollama pull qwen2.5-coder:7b" -ForegroundColor DarkGray
Write-Host ""
