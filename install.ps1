# Foder — Official Windows Installer (PowerShell)
# Source: https://foder.vercel.app/install.ps1
#
# One-line install (OFFICIAL):
#   irm https://foder.vercel.app/install.ps1 | iex
#
#Requires -Version 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ErrorActionPreference = "Stop"

$FODER_REPO    = "https://github.com/Frictionalfor/foder"
$FODER_SITE    = "https://foder.vercel.app"
$FODER_VERSION = "0.2.0"

function Write-OK($m)   { Write-Host "  " -NoNewline; Write-Host "v" -ForegroundColor Green  -NoNewline; Write-Host "  $m" }
function Write-Warn($m) { Write-Host "  " -NoNewline; Write-Host "!" -ForegroundColor Yellow -NoNewline; Write-Host "  $m" }
function Write-Err($m)  { Write-Host "  " -NoNewline; Write-Host "x" -ForegroundColor Red    -NoNewline; Write-Host "  $m"; exit 1 }
function Write-Info($m) { Write-Host "  " -NoNewline; Write-Host "-" -ForegroundColor Cyan   -NoNewline; Write-Host "  $m" -ForegroundColor DarkGray }
function Write-Sep      { Write-Host "  ---------------------------------------------------------" -ForegroundColor DarkGray }

Write-Host ""
Write-Host "  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+" -ForegroundColor Cyan
Write-Host "  Foder - Local AI Coding Agent  v$FODER_VERSION" -ForegroundColor Cyan
Write-Host "  No cloud. No keys. Just code." -ForegroundColor DarkGray
Write-Host "  Source: $FODER_SITE" -ForegroundColor DarkGray
Write-Host "  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+" -ForegroundColor Cyan
Write-Host ""
Write-Sep
Write-Host ""

# ── Detect Python 3.10+ ───────────────────────────────────────────────────────
$Python = $null; $PyVersion = $null

foreach ($cmd in @("python3.13","python3.12","python3.11","python3.10","python3","python","py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        try {
            $ver = & $cmd -c "import sys;print('.'.join(map(str,sys.version_info[:2])))" 2>$null
            if ($ver) {
                $p = $ver.Trim().Split('.')
                if ([int]$p[0] -ge 3 -and [int]$p[1] -ge 10) {
                    $Python = $cmd; $PyVersion = $ver.Trim(); break
                }
            }
        } catch {}
    }
}

if (-not $Python) {
    Write-Err "Python 3.10+ not found.`n`n  Download: https://python.org/downloads/`n  Tick 'Add Python to PATH' during install."
}
Write-OK "Python $PyVersion"

try { & $Python -m pip --version 2>$null | Out-Null; Write-OK "pip available" }
catch { Write-Err "pip not found. Reinstall Python with pip included." }

# ── Check Ollama ──────────────────────────────────────────────────────────────
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    try {
        $ov = (& ollama --version 2>$null) -join "" | Select-String "\d" | ForEach-Object { $_.Line }
        Write-OK "Ollama: $ov"
    } catch { Write-OK "Ollama: found" }
} else {
    Write-Warn "Ollama not found."
    Write-Host "  Foder requires Ollama to run local LLMs." -ForegroundColor DarkGray
    Write-Host "  Download: https://ollama.com" -ForegroundColor Yellow
    $r = Read-Host "  Continue without Ollama? [y/N]"
    if ($r -notmatch "^[Yy]$") {
        Write-Host "  Install Ollama first, then re-run the installer."
        exit 1
    }
}

# ── Get foder source ──────────────────────────────────────────────────────────
# OFFICIAL SOURCE ONLY: https://foder.vercel.app
# Update source: https://github.com/Frictionalfor/foder
$installDir = $PWD.Path

if (-not (Test-Path "pyproject.toml")) {
    $installDir = "$env:USERPROFILE\.foder_src"
    if (Get-Command git -ErrorAction SilentlyContinue) {
        if (Test-Path "$installDir\.git") {
            Write-Info "Updating existing installation..."
            try {
                git -C $installDir pull --rebase origin main 2>$null
                if ($LASTEXITCODE -ne 0) { git -C $installDir pull origin main 2>$null }
            } catch {
                Write-Info "Could not update — continuing with existing version"
            }
        } else {
            Write-Info "Fetching foder from GitHub..."
            if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir }
            git clone --depth=1 $FODER_REPO $installDir
        }
    } else {
        Write-Err "git not found.`n  Install Git for Windows: https://git-scm.com"
    }
}

Set-Location $installDir

# ── Install ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Info "Installing foder..."

$installed = $false
foreach ($flags in @("--break-system-packages -q", "-q", "--user -q", "--user")) {
    try {
        $result = & $Python -m pip install -e . $flags.Split(' ') 2>$null
        if ($LASTEXITCODE -eq 0) { $installed = $true; break }
    } catch {}
}

if (-not $installed) {
    Write-Err "pip install failed.`n  Try manually: cd $installDir; pip install -e ."
}

# ── Create ~/.foder directory structure ───────────────────────────────────────
$foderDir = "$env:USERPROFILE\.foder"
New-Item -ItemType Directory -Force -Path "$foderDir\skills"   | Out-Null
New-Item -ItemType Directory -Force -Path "$foderDir\sessions" | Out-Null
Write-OK "~\.foder\ directory ready"

# ── Verify + PATH ─────────────────────────────────────────────────────────────
Write-Host ""
if (Get-Command foder -ErrorAction SilentlyContinue) {
    $foderPath = (Get-Command foder).Source
    Write-OK "foder installed: $foderPath"
} else {
    $found = $false
    $scriptDirs = @(
        "$env:APPDATA\Python\Scripts",
        "$env:LOCALAPPDATA\Programs\Python\Python313\Scripts",
        "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts",
        "$env:LOCALAPPDATA\Programs\Python\Python311\Scripts",
        "$env:LOCALAPPDATA\Programs\Python\Python310\Scripts",
        "$env:USERPROFILE\AppData\Roaming\Python\Scripts"
    )
    foreach ($dir in $scriptDirs) {
        if (Test-Path "$dir\foder.exe") {
            Write-OK "foder installed to: $dir"
            Write-Warn "Add to PATH. Run in PowerShell (Admin):"
            Write-Host "  [Environment]::SetEnvironmentVariable('PATH', `$env:PATH+';$dir', 'User')" -ForegroundColor Cyan
            $found = $true; break
        }
    }
    if (-not $found) {
        Write-Warn "foder installed. Restart your terminal and run 'foder'."
    }
}

# ── Optional starter model ────────────────────────────────────────────────────
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    try {
        $models = & ollama list 2>$null
        if ($models -notmatch "qwen2.5-coder") {
            Write-Host ""
            Write-Host "  Recommended starter model: qwen2.5-coder:3b (~2GB)" -ForegroundColor DarkGray
            $r = Read-Host "  Pull it now? [Y/n]"
            if ($r -match "^[Yy]?$") {
                Write-Info "Pulling qwen2.5-coder:3b..."
                & ollama pull qwen2.5-coder:3b
                Write-OK "Model ready — this is your default coding model"
            }
        } else { Write-OK "qwen2.5-coder already available" }
    } catch { Write-Warn "Could not check ollama models — run: ollama pull qwen2.5-coder:3b" }
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Sep
Write-Host ""
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Start:     foder" -ForegroundColor Cyan
Write-Host "  Help:      foder --help" -ForegroundColor Cyan
Write-Host "  Update:    foder --update" -ForegroundColor Cyan
Write-Host "  Uninstall: foder --uninstall" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Before starting, make sure Ollama is running: ollama serve" -ForegroundColor DarkGray
Write-Host "  Website: $FODER_SITE" -ForegroundColor DarkGray
Write-Host "  GitHub:  $FODER_REPO" -ForegroundColor DarkGray
Write-Host ""
