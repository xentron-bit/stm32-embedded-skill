# Keil MCP Server -- Windows Installer
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$REPO_ZIP = "https://github.com/xentron-bit/stm32-embedded-skill/archive/refs/heads/main.zip"
$DEST_DIR = "$env:USERPROFILE\keil-mcp-server"
$ZIP_FILE = "$env:TEMP\stm32-skill.zip"
$EXTRACT  = "$env:TEMP\stm32-skill-extract"

# ── Language selection ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================"
Write-Host "  Keil MCP Server - Installer"
Write-Host "========================================"
Write-Host ""
Write-Host "  [1] English"
Write-Host "  [2] Turkce / Turkish"
Write-Host ""
$lang = Read-Host "  Select / Secin (1/2)"
$TR = ($lang -eq "2")

function T($en, $tr) { if ($TR) { $tr } else { $en } }

# ── winget check ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("  " + (T "Checking prerequisites..." "On kosullar kontrol ediliyor..."))

$wg = Get-Command winget -ErrorAction SilentlyContinue
if (-not $wg) {
    Write-Host ("  [ERR] " + (T "winget not found. Install 'App Installer' from Microsoft Store, then re-run." `
                                 "winget bulunamadi. Microsoft Store'dan 'App Installer' kurun, tekrar deneyin.")) -ForegroundColor Red
    Read-Host (T "Press Enter to exit" "Cikmak icin Enter")
    exit 1
}
Write-Host "  [OK]  winget" -ForegroundColor Green

# ── Python check / install ────────────────────────────────────────────────────
Write-Host ""
Write-Host ("  " + (T "Step 1/4 - Python" "Adim 1/4 - Python"))

function Find-Python {
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "C:\Python3*\python.exe",
        "C:\Python*\python.exe",
        "C:\Program Files\Python3*\python.exe",
        "C:\Program Files (x86)\Python3*\python.exe"
    )
    foreach ($p in $paths) {
        $f = Get-Item $p -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($f) {
            $v = & $f.FullName --version 2>&1
            if ($v -match "Python 3") { return $f.FullName }
        }
    }
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $v = & $pyCmd.Source --version 2>&1
        if ($v -match "Python 3") { return $pyCmd.Source }
    }
    return $null
}

$PYTHON = Find-Python

if (-not $PYTHON) {
    Write-Host ("  [!!]  " + (T "Python not found. Installing via winget..." "Python bulunamadi. winget ile kuruluyor...")) -ForegroundColor Yellow
    winget install --id Python.Python.3.12 -e --source winget --accept-source-agreements --accept-package-agreements --silent
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $PYTHON = Find-Python
    if (-not $PYTHON) {
        Write-Host ("  [ERR] " + (T "Python installed but not found. Open a new PowerShell window and re-run." `
                                     "Python kuruldu ama bulunamadi. Yeni PowerShell acip tekrar deneyin.")) -ForegroundColor Red
        Read-Host (T "Press Enter to exit" "Cikmak icin Enter")
        exit 1
    }
}

$pyVer = & $PYTHON --version 2>&1
Write-Host ("  [OK]  $pyVer  ($PYTHON)") -ForegroundColor Green

# ── Git check / install ───────────────────────────────────────────────────────
Write-Host ""
Write-Host ("  " + (T "Step 2/4 - Git" "Adim 2/4 - Git"))

$gitFound = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitFound) {
    Write-Host ("  [!!]  " + (T "Git not found. Installing via winget..." "Git bulunamadi. winget ile kuruluyor...")) -ForegroundColor Yellow
    winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements --silent
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $gitFound = Get-Command git -ErrorAction SilentlyContinue
}

if ($gitFound) {
    $gitVer = & git --version 2>&1
    Write-Host ("  [OK]  $gitVer  ($($gitFound.Source))") -ForegroundColor Green
} else {
    Write-Host ("  [!!]  " + (T "Git PATH not updated yet - continuing with ZIP download." `
                                  "Git PATH henuz guncellenmedi - ZIP ile devam ediliyor.")) -ForegroundColor Yellow
}

# ── Download & extract ────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("  " + (T "Step 3/4 - Downloading MCP server..." "Adim 3/4 - MCP sunucu indiriliyor..."))
Write-Host "  $REPO_ZIP"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $REPO_ZIP -OutFile $ZIP_FILE -UseBasicParsing
Write-Host ("  [OK]  " + (T "Download complete" "Indirme tamamlandi")) -ForegroundColor Green

if (Test-Path $EXTRACT) { Remove-Item $EXTRACT -Recurse -Force }
Expand-Archive -Path $ZIP_FILE -DestinationPath $EXTRACT -Force
$SOURCE = Join-Path $EXTRACT "stm32-embedded-skill-main\keil-mcp-server"

# Preserve any user files: backup existing DEST, then xcopy on top
if (Test-Path $DEST_DIR) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BACKUP = "$DEST_DIR.bak-$stamp"
    Write-Host ("  [!!]  " + (T "Existing dir found, backing up to $BACKUP" `
                                  "Mevcut dizin yedeklendi: $BACKUP")) -ForegroundColor Yellow
    Copy-Item -Path $DEST_DIR -Destination $BACKUP -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $DEST_DIR | Out-Null
}
# xcopy /Y /E preserves user-added files, overwrites tracked ones
& cmd /c "xcopy /E /Y /Q `"$SOURCE\*`" `"$DEST_DIR\`"" | Out-Null
Remove-Item $ZIP_FILE -Force -ErrorAction SilentlyContinue
Remove-Item $EXTRACT -Recurse -Force -ErrorAction SilentlyContinue
Write-Host ("  [OK]  $DEST_DIR") -ForegroundColor Green

# ── Run install.py ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("  " + (T "Step 4/4 - Configuring..." "Adim 4/4 - Yapilandiriliyor..."))
Set-Location $DEST_DIR
& $PYTHON -X utf8 install.py

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================"
Write-Host ("  " + (T "Done! Restart Claude, then type 'list_probes'." `
                       "Tamamlandi! Claude'u yeniden baslatin, 'list_probes' yaz.")) -ForegroundColor Green
Write-Host "========================================"
Write-Host ""
Read-Host (T "Press Enter to close" "Kapatmak icin Enter")
