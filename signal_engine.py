from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
import time
import numpy as np
import pandas as pd
import requests

SYMBOL = "BTCUSDT"
BASE_URL = "https://data-api.binance.vision/api/v3/klines"
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h"]
LIMITS = {tf: 500 for tf in TIMEFRAMES}

@dataclass
class Signal:
    timeframe: str
    bias: str
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    hold_minutes: int
    confidence: int
    note: str
    lot_examples: Dict[str, float]
    risk_lot_example: float
    risk_amount: float
    rr_tp1: float
    rr_tp2: float
    rr_tp3: float
    projected_30m_target: float
    projected_30m_note: str
    score_breakdown: Dict[str, int]
    df: pd.DataFrame

@dataclass
class MultiTimeframeSummary:
    preferred_timeframe: str
    alignment_bias: str
    alignment_score: int
    frame_biases: Dict[str, str]
    frame_confidences: Dict[str, int]
    signal: Signal

def _fetch_klines(interval: str) -> pd.DataFrame:
    params = {"symbol": SYMBOL, "interval": interval, "limit": LIMITS[interval]}
    headers = {"User-Agent": "Mozilla/5.0"}
    last_exc = None
    for _ in range(3):
        try:
            r = requests.get(BASE_URL, params=params, headers=headers, timeout=20)
            r.raise_for_status()
            raw = r.json()
            if not raw or not isinstance(raw, list):
                raise RuntimeError(f"No data for BTC {interval}")
            rows = []
            for k in raw:
                rows.append({
                    "OpenTime": pd.to_datetime(k[0], unit="ms", utc=True),
                    "Open": float(k[1]),
                    "High": float(k[2]),
                    "Low": float(k[3]),
                    "Close": float(k[4]),
                    "Volume": float(k[5]),
                })
            df = pd.DataFrame(rows).set_index("OpenTime")
            return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        except Exception as e:
            last_exc = e
            time.sleep(2)
    raise RuntimeError(f"Binance fetch failed for BTC {interval}: {last_exc}")

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"]
    df["EMA9"] = c.ewm(span=9, adjust=False).mean()
    df["EMA20"] = c.ewm(span=20, adjust=False).mean()
    df["EMA50"] = c.ewm(span=50, adjust=False).mean()

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACDSignal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACDHist"] = df["MACD"] - df["MACDSignal"]

    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        (df["High"] - df["Low"]).abs(),
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()
    return df.dropna()

def get_data(timeframe: str) -> pd.DataFrame:
    if timeframe not in TIMEFRAMES:
        raise RuntimeError(f"Unsupported timeframe: {timeframe}")
    return add_indicators(_fetch_klines(timeframe))

def _hold_minutes(timeframe: str, confidence: int) -> int:
    base = {"1m": 8, "5m": 20, "15m": 45, "30m": 90, "1h": 180, "4h": 360}[timeframe]
    return int(base * (1 + max(confidence - 5, 0) * 0.08))

def lot_profit_examples(entry: float, tp1: float) -> Dict[str, float]:
    move = abs(tp1 - entry)
    lots = [0.05, 0.10, 0.20, 0.50, 1.00]
    return {f"{lot:.2f} lot": round(move * lot, 2) for lot in lots}

def suggested_lot_by_risk(balance: float, risk_percent: float, entry: float, stop_loss: float):
    risk_amount = balance * (risk_percent / 100.0)
    stop_distance = abs(entry - stop_loss)
    if stop_distance <= 0:
        return 0.0, round(risk_amount, 2)
    lot = risk_amount / stop_distance
    lot = max(0.01, min(1.00, round(lot, 2)))
    return lot, round(risk_amount, 2)

def _score_frame(df: pd.DataFrame):
    row = df.iloc[-1]
    prev = df.iloc[-2]
    bull = {"ema": 0, "macd": 0, "hist": 0, "rsi": 0, "price": 0}
    bear = {"ema": 0, "macd": 0, "hist": 0, "rsi": 0, "price": 0}

    if row["EMA9"] > row["EMA20"] > row["EMA50"]:
        bull["ema"] = 3
    if row["EMA9"] < row["EMA20"] < row["EMA50"]:
        bear["ema"] = 3
    if row["MACD"] > row["MACDSignal"]:
        bull["macd"] = 2
    if row["MACD"] < row["MACDSignal"]:
        bear["macd"] = 2
    if row["MACDHist"] > prev["MACDHist"]:
        bull["hist"] = 1
    if row["MACDHist"] < prev["MACDHist"]:
        bear["hist"] = 1
    if 52 <= row["RSI"] <= 72:
        bull["rsi"] = 2
    if 28 <= row["RSI"] <= 48:
        bear["rsi"] = 2
    if row["Close"] > row["EMA9"]:
        bull["price"] = 1
    if row["Close"] < row["EMA9"]:
        bear["price"] = 1

    bull_score = sum(bull.values())
    bear_score = sum(bear.values())
    if bull_score >= bear_score:
        return "BUY", bull_score, bull
    return "SELL", bear_score, bear

def _project_30m_target(entry: float, atr: float, alignment_bias: str, alignment_score: int):
    strength = 0.55 + (alignment_score / 10.0)
    move = atr * strength
    if alignment_bias == "BUY":
        return round(entry + move, 2), "Expected upside bias for the next ~30 minutes if momentum holds."
    return round(entry - move, 2), "Expected downside bias for the next ~30 minutes if momentum holds."

def generate_signal(timeframe: str, balance: float = 50.0, risk_percent: float = 1.0) -> Signal:
    df = get_data(timeframe)
    bias, confidence, breakdown = _score_frame(df)
    row = df.iloc[-1]
    atr = float(row["ATR"])
    entry = float(row["Close"])

    if bias == "BUY":
        stop_loss = float(entry - 1.2 * atr)
        tp1 = float(entry + 1.5 * atr)
        tp2 = float(entry + 2.5 * atr)
        tp3 = float(entry + 4.0 * atr)
        note = f"Bullish while price stays above {row['EMA20']:.2f}"
    else:
        stop_loss = float(entry + 1.2 * atr)
        tp1 = float(entry - 1.5 * atr)
        tp2 = float(entry - 2.5 * atr)
        tp3 = float(entry - 4.0 * atr)
        note = f"Bearish while price stays below {row['EMA20']:.2f}"

    risk = abs(entry - stop_loss)
    rr1 = abs(tp1 - entry) / risk if risk else 0
    rr2 = abs(tp2 - entry) / risk if risk else 0
    rr3 = abs(tp3 - entry) / risk if risk else 0
    risk_lot, risk_amount = suggested_lot_by_risk(balance, risk_percent, entry, stop_loss)
    projected_target, projected_note = _project_30m_target(entry, atr, bias, confidence)

    return Signal(
        timeframe=timeframe,
        bias=bias,
        entry=round(entry, 2),
        stop_loss=round(stop_loss, 2),
        tp1=round(tp1, 2),
        tp2=round(tp2, 2),
        tp3=round(tp3, 2),
        hold_minutes=_hold_minutes(timeframe, confidence),
        confidence=int(confidence),
        note=note,
        lot_examples=lot_profit_examples(entry, tp1),
        risk_lot_example=risk_lot,
        risk_amount=risk_amount,
        rr_tp1=round(rr1, 2),
        rr_tp2=round(rr2, 2),
        rr_tp3=round(rr3, 2),
        projected_30m_target=projected_target,
        projected_30m_note=projected_note,
        score_breakdown=breakdown,
        df=df.tail(180).copy(),
    )

def multi_timeframe_summary(preferred_timeframe: str, balance: float = 50.0, risk_percent: float = 1.0) -> MultiTimeframeSummary:
    frame_biases = {}
    frame_confidences = {}
    buy_frames = 0
    sell_frames = 0

    for tf in TIMEFRAMES:
        sig = generate_signal(tf, balance, risk_percent)
        frame_biases[tf] = sig.bias
        frame_confidences[tf] = sig.confidence
        if sig.bias == "BUY":
            buy_frames += 1
        else:
            sell_frames += 1

    alignment_bias = "BUY" if buy_frames >= sell_frames else "SELL"
    alignment_score = max(buy_frames, sell_frames)
    preferred_signal = generate_signal(preferred_timeframe, balance, risk_percent)

    return MultiTimeframeSummary(
        preferred_timeframe=preferred_timeframe,
        alignment_bias=alignment_bias,
        alignment_score=alignment_score,
        frame_biases=frame_biases,
        frame_confidences=frame_confidences,
        signal=preferred_signal,
    )
