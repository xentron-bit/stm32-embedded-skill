@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo.
echo ========================================
echo   Keil MCP Server - Installer
echo ========================================
echo.
echo   [1] English
echo   [2] Turkce / Turkish
echo.
set /p LANG="  Secin / Select (1/2): "

if "%LANG%"=="2" (
    set "MSG_PY_CHECK=Python kontrol ediliyor..."
    set "MSG_PY_OK=Python bulundu"
    set "MSG_PY_MISS=Python bulunamadi. python.org adresinden indirin:"
    set "MSG_GIT_CHECK=Git kontrol ediliyor..."
    set "MSG_GIT_OK=Git bulundu"
    set "MSG_GIT_MISS=Git bulunamadi. git-scm.com adresinden indirin:"
    set "MSG_DL=Dosyalar indiriliyor..."
    set "MSG_DL_OK=Indirme tamamlandi"
    set "MSG_INST=Kurulum yapiliyor..."
    set "MSG_DONE=Kurulum tamamlandi! Claude'u yeniden baslatin."
    set "MSG_TEST=Test: Claude'da  list_probes  yazin."
    set "MSG_EXIT=Cikmak icin bir tusa basin..."
) else (
    set "MSG_PY_CHECK=Checking Python..."
    set "MSG_PY_OK=Python found"
    set "MSG_PY_MISS=Python not found. Download from:"
    set "MSG_GIT_CHECK=Checking Git..."
    set "MSG_GIT_OK=Git found"
    set "MSG_GIT_MISS=Git not found. Download from:"
    set "MSG_DL=Downloading files..."
    set "MSG_DL_OK=Download complete"
    set "MSG_INST=Installing..."
    set "MSG_DONE=Done! Restart Claude to use the MCP server."
    set "MSG_TEST=Test: type  list_probes  in Claude."
    set "MSG_EXIT=Press any key to exit..."
)

:: ── Step 1: Python ────────────────────────────────────────────────────────────
echo.
echo   [1/4] %MSG_PY_CHECK%

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERR] %MSG_PY_MISS%
    echo         https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=*" %%p in ('where python') do set PY_PATH=%%p
echo   [OK]  %PY_VER%
echo         %PY_PATH%

:: ── Step 2: Git ───────────────────────────────────────────────────────────────
echo.
echo   [2/4] %MSG_GIT_CHECK%

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [!!]  %MSG_GIT_MISS%
    echo         https://git-scm.com/download/win
    echo         (Git is optional - ZIP download will be used instead)
) else (
    for /f "tokens=*" %%v in ('git --version 2^>^&1') do set GIT_VER=%%v
    for /f "tokens=*" %%p in ('where git') do set GIT_PATH=%%p
    echo   [OK]  %GIT_VER%
    echo         %GIT_PATH%
)

:: ── Step 3: Download & extract ────────────────────────────────────────────────
echo.
echo   [3/4] %MSG_DL%

set ZIP_URL=https://github.com/xentron-bit/stm32-embedded-skill/archive/refs/heads/main.zip
set ZIP_FILE=%TEMP%\stm32-skill.zip
set EXTRACT=%TEMP%\stm32-embedded-skill-main
set DEST=%USERPROFILE%\keil-mcp-server

curl -L -o "%ZIP_FILE%" "%ZIP_URL%"
if %errorlevel% neq 0 (
    echo   [ERR] Download failed.
    pause
    exit /b 1
)
echo   [OK]  %MSG_DL_OK%

if exist "%EXTRACT%" rd /s /q "%EXTRACT%"
if exist "%DEST%"   rd /s /q "%DEST%"

tar -xf "%ZIP_FILE%" -C "%TEMP%"
move "%EXTRACT%\keil-mcp-server" "%DEST%" >nul
del "%ZIP_FILE%"
if exist "%EXTRACT%" rd /s /q "%EXTRACT%"

echo   [OK]  %DEST%

:: ── Step 4: install.py ───────────────────────────────────────────────────────
echo.
echo   [4/4] %MSG_INST%

cd /d "%DEST%"
python -X utf8 install.py

:: ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo ========================================
echo   %MSG_DONE%
echo   %MSG_TEST%
echo ========================================
echo.
pause
