@echo off
set "MY_DIR=%~dp0"
set "MY_DIR=%MY_DIR:~0,-1%"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo ====================================================
echo   Starting CSI Portal Services in Background...
echo ====================================================
powershell -NoProfile -Command "Start-Process -FilePath '%MY_DIR%\.venv\Scripts\python.exe' -ArgumentList 'manage.py runserver 0.0.0.0:8000' -WindowStyle Hidden -WorkingDirectory '%MY_DIR%'"
powershell -NoProfile -Command "Start-Process -FilePath '%LOCALAPPDATA%\Microsoft\WindowsApps\ngrok.exe' -ArgumentList 'http 8000 --domain=kiwi-loved-slug.ngrok-free.app' -WindowStyle Hidden -WorkingDirectory '%MY_DIR%'"
powershell -NoProfile -Command "Start-Process -FilePath '%MY_DIR%\.venv\Scripts\python.exe' -ArgumentList 'manage.py start_scheduler' -WindowStyle Hidden -WorkingDirectory '%MY_DIR%'"
echo [OK] All services started in the background!
timeout /t 3
