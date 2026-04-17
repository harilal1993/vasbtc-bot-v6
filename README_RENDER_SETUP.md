# Vas BTC Bot V6 Stable

Use on Render as a Web Service (free) or Background Worker.

## Required environment variables
- TELEGRAM_BOT_TOKEN
- TELEGRAM_ADMIN_USER_ID
- PYTHON_VERSION=3.11.11
- ALERT_INTERVAL_SECONDS=900
- HALF_HOUR_PREDICTION_SECONDS=900
- DAILY_SUMMARY_HOUR_UTC=18
- SEND_ALERT_CHARTS=false

## Health check
Set Health Check Path to `/healthz` when using Web Service.

## Notes
- Chart crash fixed
- Telegram image documents are now supported
- Scheduled alerts continue even if chart sending fails
