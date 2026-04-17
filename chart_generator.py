from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd


def render_signal_chart(signal, out_dir: str = "data/charts") -> str:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    df = signal.df.copy()
    df.index = pd.to_datetime(df.index)

    ap = [
        mpf.make_addplot(df["EMA20"], width=1),
        mpf.make_addplot(df["EMA50"], width=1),
    ]

    fig, axes = mpf.plot(
        df,
        type="candle",
        style="yahoo",
        addplot=ap,
        returnfig=True,
        volume=False,
        figsize=(12, 7),
        tight_layout=True,
        title=f"BTC / USDT {signal.timeframe.upper()}",
    )

    ax = axes[0]

    levels = [
        (signal.entry, "Entry"),
        (signal.stop_loss, "SL"),
        (signal.tp1, "TP1"),
        (signal.tp2, "TP2"),
        (signal.tp3, "TP3"),
    ]

    for y, label in levels:
        ax.axhline(y=y, linestyle="--", linewidth=0.8, alpha=0.7)
        ax.annotate(
            f"{label} {y}",
            xy=(len(df) - 1, y),
            xytext=(5, 0),
            textcoords="offset points",
            fontsize=8,
            va="center",
        )

    summary = (
        f"Bias: {signal.bias}\n"
        f"Confidence: {signal.confidence}/9\n"
        f"Target: {signal.projected_30m_target}"
    )

    ax.text(
        0.01,
        0.98,
        summary,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.8, edgecolor="gray"),
    )

    filename = out / f"btc_chart_{signal.timeframe}.png"
    fig.savefig(filename, dpi=120)
    plt.close(fig)

    return str(filename)
