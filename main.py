from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from chat_assistant import (
    answer_free_text,
    daily_summary_text,
    format_mtf,
    half_hour_prediction_text,
    screenshot_reply,
)
from chart_generator import render_signal_chart
from security import SimpleSecurity
from signal_engine import generate_signal, multi_timeframe_summary
from storage import JsonStorage

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALERT_INTERVAL_SECONDS = int(os.getenv("ALERT_INTERVAL_SECONDS", "900"))
DAILY_SUMMARY_HOUR_UTC = int(os.getenv("DAILY_SUMMARY_HOUR_UTC", "18"))
PORT = int(os.getenv("PORT", "10000"))

storage = JsonStorage()
security = SimpleSecurity()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/healthz"):
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def run_health_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        logger.info("Health server listening on port %s", PORT)
        server.serve_forever()
    except Exception:
        logger.exception("Health server failed")


def state():
    return storage.load()


def allowed(update: Update) -> bool:
    user = update.effective_user.id if update.effective_user else None
    if not security.is_admin(user):
        return False
    return security.rate_limit_ok(user)


async def reject(update: Update) -> None:
    if update.message:
        await update.message.reply_text("Unauthorized or too many requests.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    await update.message.reply_text(
        "BTC V6 bot is running.\n"
        "Commands:\n"
        "/now\n"
        "/prediction\n"
        "/chart 30m\n"
        "/balance 50\n"
        "/risk 1\n"
        "/timeframe 15m\n"
        "/status\n"
        "/summary\n"
        "/pause\n"
        "/resume"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    s = state()
    await update.message.reply_text(
        f"Paused: {s.get('paused', False)}\n"
        f"Balance: ${s.get('balance', 50):.2f}\n"
        f"Risk: {s.get('risk_percent', 1):.2f}%\n"
        f"Preferred timeframe: {s.get('preferred_timeframe', '15m')}\n"
        f"Alert interval: {ALERT_INTERVAL_SECONDS} sec"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    if not context.args:
        await update.message.reply_text("Use like: /balance 50")
        return
    try:
        bal = float(context.args[0])
        s = state()
        s["balance"] = bal
        storage.save(s)
        await update.message.reply_text(f"Balance saved: ${bal:.2f}")
    except ValueError:
        await update.message.reply_text("Invalid balance number.")


async def risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    if not context.args:
        await update.message.reply_text("Use like: /risk 1")
        return
    try:
        val = float(context.args[0])
        s = state()
        s["risk_percent"] = val
        storage.save(s)
        await update.message.reply_text(f"Risk saved: {val:.2f}%")
    except ValueError:
        await update.message.reply_text("Invalid risk number.")


async def timeframe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    if not context.args or context.args[0] not in {"1m", "5m", "15m", "30m", "1h", "4h"}:
        await update.message.reply_text("Use like: /timeframe 15m")
        return
    s = state()
    s["preferred_timeframe"] = context.args[0]
    storage.save(s)
    await update.message.reply_text(f"Preferred timeframe saved: {context.args[0]}")


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    s = state()
    s["paused"] = True
    storage.save(s)
    await update.message.reply_text("Alerts paused.")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    s = state()
    s["paused"] = False
    storage.save(s)
    await update.message.reply_text("Alerts resumed.")


async def now_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    st = state()
    try:
        summary = multi_timeframe_summary(
            st.get("preferred_timeframe", "15m"),
            st.get("balance", 50.0),
            st.get("risk_percent", 1.0),
        )
        await update.message.reply_text(format_mtf(summary))
    except Exception as e:
        logger.exception("Now command failed")
        await update.message.reply_text(f"Now command failed: {e}")


async def prediction_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    st = state()
    try:
        await update.message.reply_text(
            half_hour_prediction_text(
                st.get("balance", 50.0),
                st.get("risk_percent", 1.0),
                st.get("preferred_timeframe", "15m"),
            )
        )
    except Exception as e:
        logger.exception("Prediction failed")
        await update.message.reply_text(f"Prediction failed: {e}")


async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    st = state()
    try:
        await update.message.reply_text(
            daily_summary_text(
                st.get("balance", 50.0),
                st.get("risk_percent", 1.0),
                st.get("preferred_timeframe", "15m"),
            )
        )
    except Exception as e:
        logger.exception("Summary failed")
        await update.message.reply_text(f"Summary failed: {e}")


async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    tf = "30m"
    if context.args:
        tf = context.args[0].strip().lower()
    if tf not in {"1m", "5m", "15m", "30m", "1h", "4h"}:
        await update.message.reply_text("Supported: 1m, 5m, 15m, 30m, 1h, 4h")
        return
    st = state()
    try:
        sig = generate_signal(tf, st.get("balance", 50.0), st.get("risk_percent", 1.0))
        await update.message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        img = render_signal_chart(sig)
        with open(img, "rb") as f:
            await update.message.reply_photo(photo=f, caption=f"BTC {tf} chart ready.")
    except Exception as e:
        logger.exception("Chart failed")
        await update.message.reply_text(f"Chart failed: {e}")


async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return

    st = state()
    caption = update.message.caption or ""

    try:
        if update.message.photo:
            photos = update.message.photo
            file = await photos[-1].get_file()
            Path("data/screenshots").mkdir(parents=True, exist_ok=True)
            local_path = f"data/screenshots/{file.file_unique_id}.jpg"
            await file.download_to_drive(local_path)

        elif update.message.document:
            doc = update.message.document
            name = (doc.file_name or "").lower()
            if not (name.endswith(".jpg") or name.endswith(".jpeg") or name.endswith(".png") or (doc.mime_type or "").startswith("image/")):
                await update.message.reply_text("Please upload an image file.")
                return
            file = await doc.get_file()
            Path("data/screenshots").mkdir(parents=True, exist_ok=True)
            suffix = ".png" if name.endswith(".png") else ".jpg"
            local_path = f"data/screenshots/{file.file_unique_id}{suffix}"
            await file.download_to_drive(local_path)
        else:
            await update.message.reply_text("No screenshot received.")
            return

        await update.message.reply_text(
            screenshot_reply(
                caption,
                st.get("balance", 50.0),
                st.get("risk_percent", 1.0),
                st.get("preferred_timeframe", "15m"),
            )
        )
    except Exception as e:
        logger.exception("Screenshot analysis failed")
        await update.message.reply_text(f"Analysis failed: {e}")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not allowed(update):
        await reject(update)
        return
    text = (update.message.text or "").strip()
    low = text.lower()

    if low.startswith("balance "):
        try:
            bal = float(low.split(" ", 1)[1])
            s = state()
            s["balance"] = bal
            storage.save(s)
            await update.message.reply_text(f"Balance saved: ${bal:.2f}")
            return
        except Exception:
            await update.message.reply_text("Invalid balance format.")
            return

    if low.startswith("risk "):
        try:
            val = float(low.split(" ", 1)[1])
            s = state()
            s["risk_percent"] = val
            storage.save(s)
            await update.message.reply_text(f"Risk saved: {val:.2f}%")
            return
        except Exception:
            await update.message.reply_text("Invalid risk format.")
            return

    if low.startswith("timeframe "):
        tf = low.split(" ", 1)[1].strip()
        if tf not in {"1m", "5m", "15m", "30m", "1h", "4h"}:
            await update.message.reply_text("Supported timeframes: 1m, 5m, 15m, 30m, 1h, 4h")
            return
        s = state()
        s["preferred_timeframe"] = tf
        storage.save(s)
        await update.message.reply_text(f"Preferred timeframe saved: {tf}")
        return

    st = state()
    try:
        reply = answer_free_text(
            text,
            st.get("balance", 50.0),
            st.get("risk_percent", 1.0),
            st.get("preferred_timeframe", "15m"),
        )
        await update.message.reply_text(reply)
    except Exception as e:
        logger.exception("Request failed")
        await update.message.reply_text(f"Request failed: {e}")


async def periodic_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    s = state()
    if s.get("paused", False):
        return

    admin_id = os.getenv("TELEGRAM_ADMIN_USER_ID")
    if not admin_id:
        return

    try:
        text = half_hour_prediction_text(
            s.get("balance", 50.0),
            s.get("risk_percent", 1.0),
            s.get("preferred_timeframe", "15m"),
        )
        await context.bot.send_message(chat_id=int(admin_id), text=text)
        logger.info("15-minute alert sent successfully")
    except Exception:
        logger.exception("15-minute alert failed")


async def daily_summary_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = os.getenv("TELEGRAM_ADMIN_USER_ID")
    if not admin_id:
        return

    s = state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if s.get("daily_summary_sent_date") == today:
        return

    now_hour = datetime.now(timezone.utc).hour
    if now_hour < DAILY_SUMMARY_HOUR_UTC:
        return

    try:
        text = daily_summary_text(
            s.get("balance", 50.0),
            s.get("risk_percent", 1.0),
            s.get("preferred_timeframe", "15m"),
        )
        await context.bot.send_message(chat_id=int(admin_id), text=text)
        s["daily_summary_sent_date"] = today
        storage.save(s)
    except Exception:
        logger.exception("Daily summary job failed")


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("risk", risk))
    app.add_handler(CommandHandler("timeframe", timeframe_cmd))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("now", now_cmd))
    app.add_handler(CommandHandler("prediction", prediction_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, screenshot_handler))
    app.add_handler(MessageHandler(filters.Document.IMAGE, screenshot_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    if app.job_queue:
        app.job_queue.run_repeating(periodic_alerts, interval=ALERT_INTERVAL_SECONDS, first=60)
        app.job_queue.run_repeating(daily_summary_job, interval=3600, first=600)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
