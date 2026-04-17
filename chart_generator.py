from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from signal_engine import Signal

def render_signal_chart(signal: Signal, out_dir: str = "data/charts") -> str:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = signal.df.copy()
    df.index = pd.to_datetime(df.index)

    ap = [
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
        addplot=ap,
        returnfig=True,
        volume=False,
        panel_ratios=(5, 1.5, 1.8),
        figsize=(12, 8.5),
        title="BTC / USDT   " + signal.timeframe.upper(),
        tight_layout=True,
    )
    ax = axes[0]

    for y, label in [
        (signal.entry, "Entry"),
        (signal.stop_loss, "SL"),
        (signal.tp1, "TP1"),
        (signal.tp2, "TP2"),
        (signal.tp3, "TP3"),
        (signal.projected_30m_target, "30m Target"),
    ]:
        ax.axhline(y, linestyle="--", linewidth=1, alpha=0.85)
        ax.text(df.index[-1], y, f"  {label} {y}", va="center", fontsize=9, backgroundcolor="white")

    summary = (
        f"Bias: {signal.bias}\n"
        f"Confidence: {signal.confidence}/9\n"
        f"30m target: {signal.projected_30m_target}\n"
        f"{signal.projected_30m_note}"
    )
    ax.text(
        0.01, 0.97, summary,
        transform=ax.transAxes, va="top", ha="left", fontsize=9.5,
        bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray", alpha=0.92),
    )

    filename = out / ("btc_chart_" + signal.timeframe + ".png")
    fig.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(filename)
