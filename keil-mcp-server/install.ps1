# Keil MCP Server — Git gerektirmeyen PowerShell kurulum scripti
# Kullanim: PowerShell'de sag tik > "PowerShell ile Calistir"
# VEYA: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

$REPO_ZIP  = "https://github.com/xentron-bit/stm32-embedded-skill/archive/refs/heads/main.zip"
$DEST_DIR  = "$env:USERPROFILE\keil-mcp-server"
$ZIP_FILE  = "$env:TEMP\stm32-embedded-skill.zip"
$EXTRACT   = "$env:TEMP\stm32-embedded-skill-extract"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Keil MCP Server - Kurulum" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# 1. ZIP indir
Write-Host "`n[1/4] Repo indiriliyor..." -ForegroundColor Yellow
Write-Host "  $REPO_ZIP"
Invoke-WebRequest -Uri $REPO_ZIP -OutFile $ZIP_FILE -UseBasicParsing
Write-Host "  OK" -ForegroundColor Green

# 2. Cikart
Write-Host "`n[2/4] Dosyalar aciliyor..." -ForegroundColor Yellow
if (Test-Path $EXTRACT) { Remove-Item $EXTRACT -Recurse -Force }
Expand-Archive -Path $ZIP_FILE -DestinationPath $EXTRACT -Force

$SOURCE = Join-Path $EXTRACT "stm32-embedded-skill-main\keil-mcp-server"

if (Test-Path $DEST_DIR) { Remove-Item $DEST_DIR -Recurse -Force }
Copy-Item -Path $SOURCE -Destination $DEST_DIR -Recurse
Write-Host "  Kurulum dizini: $DEST_DIR" -ForegroundColor Green

# Temizle
Remove-Item $ZIP_FILE -Force
Remove-Item $EXTRACT -Recurse -Force

# 3. Python kontrolu
Write-Host "`n[3/4] Python kontrol ediliyor..." -ForegroundColor Yellow
$PYTHON = $null

foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $PYTHON = $cmd
            Write-Host "  OK: $ver ($cmd)" -ForegroundColor Green
            break
        }
    } catch { }
}

if (-not $PYTHON) {
    Write-Host "  HATA: Python 3 bulunamadi!" -ForegroundColor Red
    Write-Host "  Lutfen python.org adresinden Python 3.11+ kurun." -ForegroundColor Red
    Write-Host "  Kurulumdan sonra bu scripti tekrar calistirin."
    Read-Host "Devam etmek icin Enter'a basin"
    exit 1
}

# 4. install.py calistir
Write-Host "`n[4/4] MCP sunucusu kuruluyor..." -ForegroundColor Yellow
Set-Location $DEST_DIR
& $PYTHON install.py

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Kurulum tamamlandi!" -ForegroundColor Green
Write-Host "  Claude'u yeniden baslatin." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Kapatmak icin Enter'a basin"
