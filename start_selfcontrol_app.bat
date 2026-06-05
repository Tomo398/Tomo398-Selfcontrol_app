@echo off
setlocal
chcp 65001 >nul

set "APP_DIR=%~dp0"

pushd "%APP_DIR%" || (
    echo Failed to move to the application folder.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\activate.bat" (
    echo .venv\Scripts\activate.bat was not found.
    echo.
    echo Create and prepare the virtual environment first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate.bat
    echo   python -m pip install -r requirements.txt
    echo.
    pause
    popd
    exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate .venv.
    pause
    popd
    exit /b 1
)

python app.py
if errorlevel 1 (
    echo.
    echo The application exited with an error.
    pause
    popd
    exit /b 1
)

popd
exit /b 0
