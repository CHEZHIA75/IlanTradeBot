@echo off
REM ==========================================================
REM  TradeBot Launcher – Manual IB Gateway Login + Pushover
REM ==========================================================

REM === CONFIGURATION SECTION ===
set VENV_PY="C:\Users\chezh\IlanTradeBot\.venv\Scripts\python.exe"
set BOT_PATH="C:\Users\chezh\IlanTradeBot\tradebot_phase2.py"
set WORK_DIR="C:\Users\chezh\IlanTradeBot"
set LOG_FILE=%WORK_DIR%\launcher_log_%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%.txt

REM === Pushover Config ===
set PUSH_URL=https://api.pushover.net/1/messages.json
set PUSH_TOKEN=ayoidrh9v25yit1hhsfax34uws9i86
set PUSH_USER=up946v3nat6kwqjao979w4qhda42m4

REM (Optional) Email summary (if you want to keep both)
set MAIL_TO="chezhia@yahoo.com"
set MAIL_FROM="tradebot@localhost"
set SMTP_SERVER="smtp.mail.yahoo.com"

echo [%time%] === TradeBot Launcher started === > "%LOG_FILE%"
cd /d %WORK_DIR%

REM === WEEKEND SAFETY CHECK (Allow Saturday morning Sydney) ===
for /f "tokens=1" %%A in ('powershell -Command "(Get-Date).DayOfWeek"') do set DOW=%%A
if /I "%DOW%"=="Sunday" (
    echo [%time%] Weekend detected (Sunday). Exiting. >> "%LOG_FILE%"
    exit /b
)

REM === PRINT SYDNEY TIME FOR US FRIDAY 9:15AM ===
for /f %%A in ('powershell -Command ^
  "$nyTime = [datetime]::ParseExact('09:15','HH:mm',$null); " ^
  "$local = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId($nyTime,'Eastern Standard Time','AUS Eastern Standard Time'); " ^
  "$local.ToString('HH:mm')"') do set LOCAL_START=%%A
echo [%time%] Sydney time equivalent of Friday 9:15AM NY is %LOCAL_START%. >> "%LOG_FILE%"

REM === LOGIN REMINDER ===
echo [%time%] Please ensure IB Gateway is open and logged in with 2FA. >> "%LOG_FILE%"
echo Waiting 90 seconds for you to complete login...
timeout /t 90 /nobreak >nul

REM === RUN TRADEBOT ===
echo [%time%] Starting TradeBot script... >> "%LOG_FILE%"
%VENV_PY% %BOT_PATH% >> "%LOG_FILE%" 2>&1
set BOT_EXITCODE=%ERRORLEVEL%
echo [%time%] TradeBot finished with exit code %BOT_EXITCODE%. >> "%LOG_FILE%"

REM === SEND PUSHOVER NOTIFICATION ===
echo [%time%] Sending Pushover alert... >> "%LOG_FILE%"
powershell -Command ^
  "Invoke-RestMethod -Uri '%PUSH_URL%' -Method Post -Body @{token='%PUSH_TOKEN%'; user='%PUSH_USER%'; title='TradeBot Done'; message='TradeBot completed with code %BOT_EXITCODE%'}"

REM === OPTIONAL EMAIL SUMMARY ===
echo [%time%] Sending completion email... >> "%LOG_FILE%"
powershell -Command ^
    "$body = Get-Content '%LOG_FILE%' | Out-String; " ^
    "Send-MailMessage -To '%MAIL_TO%' -From '%MAIL_FROM%' -Subject 'TradeBot completed' -Body $body -SmtpServer '%SMTP_SERVER%'"

echo [%time%] === TradeBot Launcher finished === >> "%LOG_FILE%"
exit /b %BOT_EXITCODE%