# Vas BTC Bot V6 Final (Free Render Web Service)

This version is adjusted for free Render Web Service deployment.

## Fixes included
- Uses Binance Vision public market data endpoint
- Starts a tiny HTTP health server for Render on PORT
- Telegram polling bot remains unchanged

## Render settings
- Service type: Web Service
- Build command: `pip install -r requirements.txt`
- Start command: `python main.py`
- Health check path: `/healthz`

## Required environment variables
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ADMIN_USER_ID` (optional for first test; remove if access issue)
- `PYTHON_VERSION=3.11.11`
- `ALERT_INTERVAL_SECONDS=900` or `1800`
- `HALF_HOUR_PREDICTION_SECONDS=900` or `1800`
- `DAILY_SUMMARY_HOUR_UTC=18`

## Important security note
If your bot token appeared in logs or screenshots, regenerate it in BotFather and update `TELEGRAM_BOT_TOKEN` immediately.
