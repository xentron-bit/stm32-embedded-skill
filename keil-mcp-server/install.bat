@echo off
setlocal EnableDelayedExpansion

echo.
echo ========================================
echo   Keil MCP Server - Installer
echo ========================================
echo.
echo   [1] English
echo   [2] Turkce / Turkish
echo.
set /p LANG=  Secin / Select (1/2):

if "!LANG!"=="2" (
    set "L_PYTHON=Python kontrol ediliyor"
    set "L_PYTHON_ERR=Python bulunamadi! Indirin:"
    set "L_GIT=Git kontrol ediliyor"
    set "L_GIT_WARN=Git bulunamadi (opsiyonel)"
    set "L_DOWNLOAD=Dosyalar indiriliyor"
    set "L_INSTALL=Kurulum yapiliyor"
    set "L_DONE=Kurulum tamamlandi! Claude'u yeniden baslatin."
    set "L_TEST=Test: Claude'da  list_probes  yazin."
) else (
    set "L_PYTHON=Checking Python"
    set "L_PYTHON_ERR=Python not found! Download from:"
    set "L_GIT=Checking Git"
    set "L_GIT_WARN=Git not found (optional)"
    set "L_DOWNLOAD=Downloading files"
    set "L_INSTALL=Installing"
    set "L_DONE=Done! Restart Claude."
    set "L_TEST=Test: type  list_probes  in Claude."
)

echo.
echo ----------------------------------------
echo   1/4  !L_PYTHON!
echo ----------------------------------------

python --version 2>nul
if errorlevel 1 (
    echo   [ERR] !L_PYTHON_ERR!
    echo         https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [OK]  %%v
for /f "tokens=*" %%p in ('where python') do echo         %%p

echo.
echo ----------------------------------------
echo   2/4  !L_GIT!
echo ----------------------------------------

git --version 2>nul
if errorlevel 1 (
    echo   [!!]  !L_GIT_WARN!
    echo         https://git-scm.com/download/win
) else (
    for /f "tokens=*" %%v in ('git --version 2^>^&1') do echo   [OK]  %%v
    for /f "tokens=*" %%p in ('where git') do echo         %%p
)

echo.
echo ----------------------------------------
echo   3/4  !L_DOWNLOAD!
echo ----------------------------------------

set "ZIP_URL=https://github.com/xentron-bit/stm32-embedded-skill/archive/refs/heads/main.zip"
set "ZIP_FILE=%TEMP%\stm32-skill.zip"
set "EXTRACT=%TEMP%\stm32-embedded-skill-main"
set "DEST=%USERPROFILE%\keil-mcp-server"

echo   %ZIP_URL%
curl -L -o "%ZIP_FILE%" "%ZIP_URL%"
if errorlevel 1 (
    echo   [ERR] Download failed.
    pause
    exit /b 1
)
echo   [OK]  Download complete

if exist "%EXTRACT%" rd /s /q "%EXTRACT%"
tar -xf "%ZIP_FILE%" -C "%TEMP%"
if not exist "%DEST%" mkdir "%DEST%"
xcopy /E /Y /Q "%EXTRACT%\keil-mcp-server\*" "%DEST%\" >nul
del "%ZIP_FILE%" 2>nul
if exist "%EXTRACT%" rd /s /q "%EXTRACT%"
echo   [OK]  %DEST%

echo.
echo ----------------------------------------
echo   4/4  !L_INSTALL!
echo ----------------------------------------

cd /d "%DEST%"
python -X utf8 install.py

echo.
echo ========================================
echo   !L_DONE!
echo   !L_TEST!
echo ========================================
echo.
pause
