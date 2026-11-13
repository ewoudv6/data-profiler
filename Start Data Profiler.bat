@echo off
REM Double-click this file to start the Data Profiler app in your browser.
REM Close this window (or press Ctrl + C in it) to stop the app.

REM Go to the folder this file is in, so it works from anywhere (also from a shortcut).
cd /d "%~dp0"

REM First time only: create a private Python install (.venv) with the needed packages.
if not exist ".venv\Scripts\python.exe" (
    echo First start: setting things up. This takes a few minutes, only once...
    echo.
    py -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo Could not find Python. Install it from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH" during the installation. Then try again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Installing the packages failed. See the messages above.
        rmdir /s /q .venv
        pause
        exit /b 1
    )
    echo.
)

echo Starting the Data Profiler... your browser will open in a moment.
echo Keep this window open while you use the app. Close it to stop the app.
echo.

".venv\Scripts\python.exe" -m streamlit run profiler_app.py --browser.gatherUsageStats false --server.showEmailPrompt false

REM If something went wrong, keep the window open so you can read the error.
if errorlevel 1 pause
