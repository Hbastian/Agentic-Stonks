# =============================================================
# SIMPLE STOCK ADVISOR — Educational RSI-Based Stock Checker
# =============================================================
# Overview:
# - Uses Yahoo Finance data (3-month price history)
# - Computes RSI manually (avg gain vs. avg loss)
# - Provides a simple BUY/HOLD/SELL-style recommendation
#   · Overbought  (RSI > 70) → HOLD / SELL
#   · Oversold    (RSI < 30) → BUY / WATCH CLOSELY
#   · Neutral     (30 ≤ RSI ≤ 70) → HOLD / MONITOR
#
# Notes:
# - This script is intentionally simple and **education-only**.
# - It is NOT financial advice.
# =============================================================

import yfinance as yf

print("=== SMART STOCK ADVISOR ===")
print("Helping you make better investment decisions!")
print()


# -------------------------------------------------------------
# simple_stock_check(stock_symbol)
# -------------------------------------------------------------
# Inputs:
#   stock_symbol : str
#
# Responsibilities:
#   1. Fetch 3 months of historical OHLCV data using yfinance
#   2. Extract closing prices
#   3. Compute daily price changes
#   4. Separate gains vs. losses
#   5. Compute average gain/loss → RSI formula
#   6. Print a human-readable recommendation
#
# Returns:
#   float (RSI value) or None if data unavailable
#
# Error Handling:
#   - Missing ticker data
#   - Zero-gain or zero-loss periods
#   - yfinance API errors
# -------------------------------------------------------------
def simple_stock_check(stock_symbol):
    """
    Analyze stock health using a simple RSI calculation and
    produce educational investment-style recommendations.
    """

    print(f"Analyzing {stock_symbol}...")

    try:
        # -----------------------------------------------------
        # Fetch price history (3 months of daily closes)
        # -----------------------------------------------------
        stock = yf.Ticker(stock_symbol)
        price_history = stock.history(period="3mo")

        if price_history.empty:
            print(f"   Could not find data for {stock_symbol}. Please check the symbol.")
            return None

        # Extract closing prices
        prices = price_history["Close"]
        current_price = prices.iloc[-1]

        print(f"   Current Price: ${current_price:.2f}")
        print(f"   Data Period: {len(prices)} trading days")

        # -----------------------------------------------------
        # Compute daily price changes
        # -----------------------------------------------------
        price_changes = []
        for i in range(1, len(prices)):
            change = prices.iloc[i] - prices.iloc[i - 1]
            price_changes.append(change)

        # Separate gains and losses
        gaining_days = [chg for chg in price_changes if chg > 0]
        losing_days = [chg for chg in price_changes if chg < 0]

        if len(gaining_days) == 0 or len(losing_days) == 0:
            print("   Still gathering data on this stock...")
            return None

        # -----------------------------------------------------
        # Average gain / average loss → RSI Calculation
        # -----------------------------------------------------
        avg_gains = sum(gaining_days) / len(gaining_days)
        avg_losses = abs(sum(losing_days) / len(losing_days))

        if avg_losses == 0:
            rsi_score = 100
        else:
            strength_ratio = avg_gains / avg_losses
            rsi_score = 100 - (100 / (1 + strength_ratio))

        print(f"   RSI Health Score: {rsi_score:.1f}/100")

        # -----------------------------------------------------
        # Interpretation & Recommendation
        # -----------------------------------------------------
        if rsi_score > 70:
            print("   RECOMMENDATION: HOLD or SELL")
            print("   Reason: Stock may be overvalued and due for correction")
            print("   Technical Signal: Overbought condition")

        elif rsi_score < 30:
            print("   RECOMMENDATION: BUY or WATCH CLOSELY")
            print("   Reason: Stock may be undervalued with growth potential")
            print("   Technical Signal: Oversold condition")

        else:
            print("   RECOMMENDATION: HOLD and MONITOR")
            print("   Reason: Stock trading in normal range")
            print("   Technical Signal: Neutral momentum")

        print("=" * 50)
        return rsi_score

    except Exception as e:
        print(f"   Error analyzing {stock_symbol}: {e}")
        print("   Please try again later")
        return None


# -------------------------------------------------------------
# On-Startup Guide
# -------------------------------------------------------------
print("HOW THIS ANALYSIS WORKS:")
print("- Uses RSI (Relative Strength Index) to measure stock momentum")
print("- Scores range from 0–100 with clear investment signals")
print("- Based on the last 3 months of real market data")
print()

print("READY TO ANALYZE STOCKS!")
print("=" * 40)


# -------------------------------------------------------------
# Batch Analysis of Popular Stocks
# -------------------------------------------------------------
stocks_to_analyze = ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "NFLX"]

for stock in stocks_to_analyze:
    simple_stock_check(stock)

print()
print("ANALYSIS COMPLETE!")
