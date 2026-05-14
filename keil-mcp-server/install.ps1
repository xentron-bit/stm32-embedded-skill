# Keil MCP Server -- Full Auto Installer for Windows
# No prerequisites required: installs Git, Python, and the MCP server automatically.
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$REPO_ZIP  = "https://github.com/xentron-bit/stm32-embedded-skill/archive/refs/heads/main.zip"
$DEST_DIR  = "$env:USERPROFILE\keil-mcp-server"
$ZIP_FILE  = "$env:TEMP\stm32-skill.zip"
$EXTRACT   = "$env:TEMP\stm32-skill-extract"

# ════════════════════════════════════════════════════════════════════════════
# LANGUAGE SELECTION
# ════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Keil MCP Server - Installer"           -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  [1] English"
Write-Host "  [2] Turkce / Turkish"
Write-Host ""
$langChoice = Read-Host "  Select language / Dil secin (1/2)"

$TR = ($langChoice -eq "2")

function msg($en, $tr) { if ($TR) { return $tr } else { return $en } }

# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

function Print-Header($text) {
    Write-Host ""
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("  " + "-" * ($text.Length)) -ForegroundColor DarkGray
}

function Print-OK($text)   { Write-Host "  [OK]  $text" -ForegroundColor Green }
function Print-WARN($text) { Write-Host "  [!!]  $text" -ForegroundColor Yellow }
function Print-ERR($text)  { Write-Host "  [ERR] $text" -ForegroundColor Red }
function Print-INFO($text) { Write-Host "        $text" -ForegroundColor Gray }

# ════════════════════════════════════════════════════════════════════════════
# STEP 0: Check & install winget (prerequisite for all auto-installs)
# ════════════════════════════════════════════════════════════════════════════
Print-Header (msg "Checking prerequisites" "On kosullar kontrol ediliyor")

$hasWinget = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
if ($hasWinget) {
    Print-OK (msg "winget found" "winget mevcut")
} else {
    Print-WARN (msg "winget not found. It ships with Windows 10 1709+." `
                    "winget bulunamadi. Windows 10 1709+ ile gelir.")
    Print-INFO (msg "Install App Installer from Microsoft Store, then re-run this script." `
                    "Microsoft Store'dan 'App Installer' kurun, sonra scripti tekrar calistirin.")
    Read-Host (msg "Press Enter to exit" "Cikmak icin Enter'a basin")
    exit 1
}

# ════════════════════════════════════════════════════════════════════════════
# STEP 1: Python check / install
# ════════════════════════════════════════════════════════════════════════════
Print-Header (msg "Step 1/4 - Python" "Adim 1/4 - Python")

function Find-Python {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\python.exe",
        "C:\Python3*\python.exe",
        "C:\Python*\python.exe",
        "C:\Program Files\Python3*\python.exe",
        "C:\Program Files (x86)\Python3*\python.exe",
        "C:\Program Files (Arm)\Python3*\python.exe",
        "$env:APPDATA\Python\Python3*\Scripts\python.exe"
    )
    foreach ($pat in $candidates) {
        $found = Get-Item $pat -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $ver = & $found.FullName --version 2>&1
            if ($ver -match "Python 3") { return $found.FullName }
        }
    }
    # py launcher
    try {
        $pyExe = (Get-Command py -ErrorAction Stop).Source
        $ver = & $pyExe --version 2>&1
        if ($ver -match "Python 3") { return $pyExe }
    } catch {}
    return $null
}

$PYTHON = Find-Python

if ($PYTHON) {
    $pyVer = & $PYTHON --version 2>&1
    Print-OK "$pyVer"
    Print-INFO (msg "Path: $PYTHON" "Yol: $PYTHON")
} else {
    Print-WARN (msg "Python not found. Installing Python 3.12 via winget..." `
                    "Python bulunamadi. winget ile Python 3.12 kuruluyor...")
    winget install --id Python.Python.3.12 -e --source winget `
          --accept-source-agreements --accept-package-agreements --silent
    # Refresh PATH in current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    $PYTHON = Find-Python
    if (-not $PYTHON) {
        Print-ERR (msg "Python installed but still not found. Open a new PowerShell window and re-run." `
                       "Python kuruldu ama hala bulunamadi. Yeni bir PowerShell acip tekrar deneyin.")
        Read-Host (msg "Press Enter to exit" "Cikmak icin Enter'a basin")
        exit 1
    }
    $pyVer = & $PYTHON --version 2>&1
    Print-OK "$pyVer"
    Print-INFO (msg "Path: $PYTHON" "Yol: $PYTHON")
}

# ════════════════════════════════════════════════════════════════════════════
# STEP 2: Git check / install
# ════════════════════════════════════════════════════════════════════════════
Print-Header (msg "Step 2/4 - Git" "Adim 2/4 - Git")

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
$gitExe = if ($gitCmd) { $gitCmd.Source } else { $null }

if ($gitExe) {
    $gitVer = & git --version 2>&1
    Print-OK "$gitVer"
    Print-INFO (msg "Path: $gitExe" "Yol: $gitExe")
} else {
    Print-WARN (msg "Git not found. Installing Git via winget..." `
                    "Git bulunamadi. winget ile kuruluyor...")
    winget install --id Git.Git -e --source winget `
          --accept-source-agreements --accept-package-agreements --silent
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    $gitExe = if ($gitCmd) { $gitCmd.Source } else { $null }
    if ($gitExe) {
        $gitVer = & git --version 2>&1
        Print-OK "$gitVer"
        Print-INFO (msg "Path: $gitExe" "Yol: $gitExe")
    } else {
        Print-WARN (msg "Git installed but PATH not updated yet. Continuing without Git (ZIP download will be used)." `
                        "Git kuruldu ama PATH henuz guncellenmedi. ZIP indirme kullanilacak.")
    }
}

# ════════════════════════════════════════════════════════════════════════════
# STEP 3: Download & extract MCP server
# ════════════════════════════════════════════════════════════════════════════
Print-Header (msg "Step 3/4 - Download MCP server" "Adim 3/4 - MCP sunucu indiriliyor")

Print-INFO $REPO_ZIP
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    Invoke-WebRequest -Uri $REPO_ZIP -OutFile $ZIP_FILE -UseBasicParsing
    Print-OK (msg "Download complete" "Indirme tamamlandi")
} catch {
    Print-ERR (msg "Download failed: $_" "Indirme basarisiz: $_")
    Read-Host (msg "Press Enter to exit" "Cikmak icin Enter'a basin")
    exit 1
}

if (Test-Path $EXTRACT) { Remove-Item $EXTRACT -Recurse -Force }
Expand-Archive -Path $ZIP_FILE -DestinationPath $EXTRACT -Force
$SOURCE = Join-Path $EXTRACT "stm32-embedded-skill-main\keil-mcp-server"
if (Test-Path $DEST_DIR) { Remove-Item $DEST_DIR -Recurse -Force }
Copy-Item -Path $SOURCE -Destination $DEST_DIR -Recurse
Remove-Item $ZIP_FILE  -Force -ErrorAction SilentlyContinue
Remove-Item $EXTRACT   -Recurse -Force -ErrorAction SilentlyContinue
Print-OK (msg "Installed to: $DEST_DIR" "Kurulum dizini: $DEST_DIR")

# ════════════════════════════════════════════════════════════════════════════
# STEP 4: Run install.py
# ════════════════════════════════════════════════════════════════════════════
Print-Header (msg "Step 4/4 - Configuring MCP server" "Adim 4/4 - MCP sunucu yapilandiriliyor")

Set-Location $DEST_DIR
& $PYTHON -X utf8 install.py

# ════════════════════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($TR) {
    Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
    Write-Host "  Claude Code CLI veya Claude Desktop'i" -ForegroundColor Green
    Write-Host "  yeniden baslatin." -ForegroundColor Green
    Write-Host "  Test: Claude'da 'list_probes' yaz." -ForegroundColor Green
} else {
    Write-Host "  Installation complete!" -ForegroundColor Green
    Write-Host "  Restart Claude Code CLI or Claude Desktop." -ForegroundColor Green
    Write-Host "  Test: type 'list_probes' in Claude." -ForegroundColor Green
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Read-Host (msg "Press Enter to close" "Kapatmak icin Enter'a basin")
