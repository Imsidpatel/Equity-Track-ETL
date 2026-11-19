import os
import yfinance as yf
import pandas as pd
from supabase import create_client

# Connect to Supabase using GitHub Secrets
supabase = create_client(
    os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# Nifty 50 watchlist (NSE tickers end with .NS)
WATCHLIST = {
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "Tata Consultancy Services",
    "HDFCBANK.NS": "HDFC Bank",
    "INFY.NS": "Infosys",
    "ICICIBANK.NS": "ICICI Bank",
    "TATAMOTORS.NS": "Tata Motors",
    "SUNPHARMA.NS": "Sun Pharma",
}


def calculate_rsi(series: pd.Series, period: int = 14) -> float:
    """Compute the 14-day Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def evaluate_stock(price: float, sma_50: float, rsi: float) -> tuple[str, str]:
    """Rule-based investment signal generator."""
    if rsi < 35 and price > sma_50 * 0.95:
        return "STRONG BUY", f"Oversold dip (RSI {rsi}) near 50-DMA support"
    elif price > sma_50 and 45 <= rsi <= 68:
        return "ACCUMULATE", f"Healthy uptrend above 50-DMA with balanced momentum (RSI {rsi})"
    elif rsi > 72:
        return "OVERBOUGHT / WAIT", f"Overextended momentum (RSI {rsi}); wait for pullback"
    else:
        return "HOLD / WATCH", f"Trading below 50-DMA (RSI {rsi}); wait for trend reversal"


def run_pipeline():
    records = []

    for ticker, name in WATCHLIST.items():
        # 1. EXTRACT: Fetch 3 months of daily historical data
        df = yf.Ticker(ticker).history(period="3mo")
        if len(df) < 50:
            continue

        # 2. TRANSFORM: Calculate price metrics & technical indicators
        close_price = round(float(df["Close"].iloc[-1]), 2)
        prev_close = float(df["Close"].iloc[-2])
        daily_change = round(
            ((close_price - prev_close) / prev_close) * 100, 2)
        sma_50 = round(
            float(df["Close"].rolling(window=50).mean().iloc[-1]), 2)
        rsi_14 = calculate_rsi(df["Close"])

        signal, reason = evaluate_stock(close_price, sma_50, rsi_14)

        records.append({
            "ticker": ticker,
            "company_name": name,
            "close_price_inr": close_price,
            "daily_change_pct": daily_change,
            "sma_50": sma_50,
            "rsi_14": rsi_14,
            "investment_signal": signal,
            "verdict_reason": reason,
        })

    # 3. LOAD: Push daily analysis to Supabase
    if records:
        supabase.table("daily_stock_signals").insert(records).execute()
        print(f"Successfully analyzed and uploaded {len(records)} NSE stocks.")

        top_picks = [r for r in records if r["investment_signal"]
                     in ("STRONG BUY", "ACCUMULATE")]
        print("Today's Top Investment Candidates:",
              [p["ticker"] for p in top_picks])


if __name__ == "__main__":
    run_pipeline()
