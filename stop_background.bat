@echo off
echo Stopping Telegram Site Management Bot...
taskkill /f /im pythonw.exe 2>nul
echo Bot stopped.
timeout /t 3
