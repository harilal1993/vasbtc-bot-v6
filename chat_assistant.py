from __future__ import annotations
from signal_engine import generate_signal, multi_timeframe_summary

def format_signal(s) -> str:
    profits = ", ".join(f"{k}=${v}" for k, v in s.lot_examples.items())
    breakdown = ", ".join(f"{k}:{v}" for k, v in s.score_breakdown.items())
    return (
        f"BTC {s.timeframe} signal\n"
        f"Bias: {s.bias}\n"
        f"Entry: {s.entry}\n"
        f"SL: {s.stop_loss}\n"
        f"TP1: {s.tp1} (R:R {s.rr_tp1})\n"
        f"TP2: {s.tp2} (R:R {s.rr_tp2})\n"
        f"TP3: {s.tp3} (R:R {s.rr_tp3})\n"
        f"Projected next 30m target: {s.projected_30m_target}\n"
        f"{s.projected_30m_note}\n"
        f"Hold: about {s.hold_minutes} min\n"
        f"Confidence: {s.confidence}/9\n"
        f"Suggested lot by risk: {s.risk_lot_example:.2f}\n"
        f"Risk amount used: ${s.risk_amount:.2f}\n"
        f"TP1 example profits: {profits}\n"
        f"Score breakdown: {breakdown}\n"
        f"{s.note}"
    )

def format_mtf(summary) -> str:
    order = ["1m", "5m", "15m", "30m", "1h", "4h"]
    frame_bits = " | ".join(f"{tf}:{summary.frame_biases[tf]}({summary.frame_confidences[tf]})" for tf in order)
    return (
        "BTC multi-timeframe summary\n"
        f"Alignment bias: {summary.alignment_bias}\n"
        f"Alignment score: {summary.alignment_score}/6\n"
        f"{frame_bits}\n\n"
        f"{format_signal(summary.signal)}"
    )

def half_hour_prediction_text(balance: float, risk_percent: float, preferred_timeframe: str = "15m") -> str:
    summary = multi_timeframe_summary(preferred_timeframe, balance, risk_percent)
    s = summary.signal
    direction = "upward" if summary.alignment_bias == "BUY" else "downward"
    return (
        "30-minute BTC prediction\n\n"
        f"Overall trend: {direction}\n"
        f"Frames used: 1m, 5m, 15m, 30m, 1h, 4h\n"
        f"Alignment: {summary.alignment_score}/6\n"
        f"Current price: {s.entry}\n"
        f"Projected 30m target: {s.projected_30m_target}\n"
        f"{s.projected_30m_note}\n"
        f"Trading bias now: {s.bias}\n"
        f"Protection level: {s.stop_loss}\n"
        f"Upside checkpoints: {s.tp1}, {s.tp2}, {s.tp3}"
    )

def daily_summary_text(balance: float, risk_percent: float, preferred_timeframe: str = "15m") -> str:
    summary = multi_timeframe_summary(preferred_timeframe, balance, risk_percent)
    return "Daily summary\n\n" + format_mtf(summary)

def answer_free_text(text: str, balance: float, risk_percent: float, preferred_timeframe: str = "15m") -> str:
    t = text.strip().lower()
    if "prediction" in t or "trend" in t or "now" in t:
        return format_mtf(multi_timeframe_summary(preferred_timeframe, balance, risk_percent))
    if "30m" in t or "half hour" in t:
        return half_hour_prediction_text(balance, risk_percent, preferred_timeframe)
    if "summary" in t:
        return daily_summary_text(balance, risk_percent, preferred_timeframe)
    if "0.05" in t or "0.1" in t or "0.10" in t or "0.2" in t or "0.20" in t or "0.5" in t or "1 lot" in t:
        s = generate_signal(preferred_timeframe, balance, risk_percent)
        return "TP1 example profits: " + ", ".join(f"{k}=${v}" for k, v in s.lot_examples.items())
    return (
        "I can help with:\n"
        "- now\n"
        "- trend\n"
        "- 30m prediction\n"
        "- daily summary\n"
        "- balance 100\n"
        "- risk 1.5\n"
        "- timeframe 5m\n"
        "- chart 30m"
    )

def screenshot_reply(caption: str, balance: float, risk_percent: float, preferred_timeframe: str = "15m") -> str:
    summary = multi_timeframe_summary(preferred_timeframe, balance, risk_percent)
    s = summary.signal
    support = min(s.entry, s.stop_loss)
    resistance = max(s.tp1, s.tp2, s.tp3)
    return (
        "Screenshot received for BTC.\n"
        f"Alignment bias: {summary.alignment_bias} ({summary.alignment_score}/6)\n"
        f"Projected next 30m target: {s.projected_30m_target}\n"
        f"Support zone: {support:.2f}\n"
        f"Resistance zone: {resistance:.2f}\n"
        f"{s.projected_30m_note}"
    )
