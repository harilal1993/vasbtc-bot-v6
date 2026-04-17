from __future__ import annotations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from signal_engine import Signal

SUPPORTED_TF = {"1m", "5m", "15m", "30m", "1h", "4h"}


def _safe_dataframe(signal: Signal) -> pd.DataFrame:
    df = signal.df.copy().tail(120)
    df.index = pd.to_datetime(df.index)
    needed = [
        "Open", "High", "Low", "Close", "Volume",
        "EMA20", "EMA50", "RSI", "MACD", "MACDSignal",
    ]
    for col in needed:
        if col not in df.columns:
            raise ValueError(f"Missing chart column: {col}")
    return df


def render_signal_chart(signal: Signal, out_dir: str = "data/charts") -> str:
    if signal.timeframe not in SUPPORTED_TF:
        raise ValueError(f"Unsupported timeframe for chart: {signal.timeframe}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = _safe_dataframe(signal)

    addplots = [
        mpf.make_addplot(df["EMA20"], width=1.0),
        mpf.make_addplot(df["EMA50"], width=1.0),
        mpf.make_addplot(df["RSI"], panel=1, ylabel="RSI"),
        mpf.make_addplot(df["MACD"], panel=2, ylabel="MACD"),
        mpf.make_addplot(df["MACDSignal"], panel=2),
    ]

    fig, axes = mpf.plot(
        df,
        type="candle",
        style="yahoo",
        addplot=addplots,
        returnfig=True,
        volume=False,
        panel_ratios=(5, 1.5, 1.8),
        figsize=(12, 8),
        title=f"BTC / USDT  {signal.timeframe.upper()}",
        tight_layout=False,
    )
    ax = axes[0]

    levels = [
        (signal.entry, "Entry"),
        (signal.stop_loss, "SL"),
        (signal.tp1, "TP1"),
        (signal.tp2, "TP2"),
        (signal.tp3, "TP3"),
        (signal.projected_30m_target, "30m Target"),
    ]

    y_transform = ax.get_yaxis_transform()
    for y, label in levels:
        ax.axhline(y, linestyle="--", linewidth=0.9, alpha=0.8)
        ax.text(
            0.995,
            y,
            f" {label} {y:.2f}",
            transform=y_transform,
            va="center",
            ha="right",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="gray", alpha=0.9),
            clip_on=True,
        )

    summary = (
        f"Bias: {signal.bias}
"
        f"Confidence: {signal.confidence}/9
"
        f"30m target: {signal.projected_30m_target:.2f}
"
        f"SL: {signal.stop_loss:.2f}"
    )
    ax.text(
        0.01,
        0.98,
        summary,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8.5,
        bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray", alpha=0.92),
    )

    fig.subplots_adjust(left=0.07, right=0.93, top=0.92, bottom=0.08)
    filename = out / f"btc_chart_{signal.timeframe}.png"
    fig.savefig(filename, dpi=110)
    plt.close(fig)
    return str(filename)
