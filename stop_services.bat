@echo off
echo ====================================================
echo   Stopping CSI Portal Services...
echo ====================================================
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'Name = ''python.exe''' | Where-Object { $_.CommandLine -like '*runserver*' -or $_.CommandLine -like '*start_scheduler*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
powershell -NoProfile -Command "Stop-Process -Name 'ngrok' -Force -ErrorAction SilentlyContinue"
echo [OK] All services stopped!
timeout /t 3
