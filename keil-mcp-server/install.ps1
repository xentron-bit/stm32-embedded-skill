# Keil MCP Server — Tam otomatik PowerShell kurulum
# Git veya Python gerektirmez; hepsini otomatik kurar.
# Kullanim: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

$REPO_ZIP = "https://github.com/xentron-bit/stm32-embedded-skill/archive/refs/heads/main.zip"
$DEST_DIR = "$env:USERPROFILE\keil-mcp-server"
$ZIP_FILE = "$env:TEMP\stm32-skill.zip"
$EXTRACT  = "$env:TEMP\stm32-skill-extract"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Keil MCP Server - Kurulum" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# ── Yardimci: gercek Python bul (Store stub degil) ──────────────────────────
function Find-Python {
    # Bilinen gercek Python konumlari (Store stub'i atla)
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\python.exe",
        "C:\Python3*\python.exe",
        "C:\Python*\python.exe",
        "C:\Program Files\Python*\python.exe",
        "C:\Program Files (x86)\Python*\python.exe",
        "C:\Program Files (Arm)\Python*\python.exe",
        "$env:APPDATA\Python\Python*\Scripts\python.exe"
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

# ── 1. Repo ZIP indir ────────────────────────────────────────────────────────
Write-Host "`n[1/5] Repo indiriliyor..." -ForegroundColor Yellow
Write-Host "  $REPO_ZIP"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $REPO_ZIP -OutFile $ZIP_FILE -UseBasicParsing
Write-Host "  OK" -ForegroundColor Green

# ── 2. Cikart ve kopyala ────────────────────────────────────────────────────
Write-Host "`n[2/5] Dosyalar aciliyor..." -ForegroundColor Yellow
if (Test-Path $EXTRACT) { Remove-Item $EXTRACT -Recurse -Force }
Expand-Archive -Path $ZIP_FILE -DestinationPath $EXTRACT -Force
$SOURCE = Join-Path $EXTRACT "stm32-embedded-skill-main\keil-mcp-server"
if (Test-Path $DEST_DIR) { Remove-Item $DEST_DIR -Recurse -Force }
Copy-Item -Path $SOURCE -Destination $DEST_DIR -Recurse
Remove-Item $ZIP_FILE -Force -ErrorAction SilentlyContinue
Remove-Item $EXTRACT -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  Kurulum dizini: $DEST_DIR" -ForegroundColor Green

# ── 3. Python bul / kur ──────────────────────────────────────────────────────
Write-Host "`n[3/5] Python kontrol ediliyor..." -ForegroundColor Yellow
$PYTHON = Find-Python

if (-not $PYTHON) {
    Write-Host "  Python bulunamadi. winget ile kuruluyor..." -ForegroundColor Yellow

    # winget mevcut mu?
    $wg = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wg) {
        Write-Host "  HATA: winget de yok. Python'u elle kurun:" -ForegroundColor Red
        Write-Host "  https://www.python.org/downloads/" -ForegroundColor Red
        Read-Host "Kurulumdan sonra bu scripti tekrar calistirin. Enter ile cikin"
        exit 1
    }

    Write-Host "  winget install Python.Python.3.12 ..."
    winget install --id Python.Python.3.12 -e --source winget `
          --accept-source-agreements --accept-package-agreements --silent

    # PATH'i guncelle (current session icin)
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")

    $PYTHON = Find-Python
    if (-not $PYTHON) {
        Write-Host "  HATA: Python kuruldu ama hala bulunamadi." -ForegroundColor Red
        Write-Host "  Yeni bir PowerShell penceresi acip tekrar deneyin." -ForegroundColor Red
        Read-Host "Enter ile cikin"
        exit 1
    }
}

$pyVer = & $PYTHON --version 2>&1
Write-Host "  OK: $pyVer" -ForegroundColor Green
Write-Host "  Yol: $PYTHON" -ForegroundColor Gray

# ── 4. install.py calistir ──────────────────────────────────────────────────
Write-Host "`n[4/5] pip + MCP kaydi yapiliyor..." -ForegroundColor Yellow
Set-Location $DEST_DIR
& $PYTHON install.py

# ── 5. Ozet ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
Write-Host "  Claude Code CLI'yi veya Claude Desktop'i" -ForegroundColor Green
Write-Host "  yeniden baslatin." -ForegroundColor Green
Write-Host "  Test: Claude'da 'list_probes' yaz." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Kapatmak icin Enter'a basin"
