# analysis.py
import yfinance as yf


def analyze_rsi(stock_symbol):
    stock = yf.Ticker(stock_symbol)
    prices = stock.history(period="3mo")['Close']
    if prices.empty:
        return "No data", None

    price_changes = prices.diff().dropna()
    gains = price_changes.where(price_changes > 0, 0)
    losses = -price_changes.where(price_changes < 0, 0)

    avg_gain = gains.mean()
    avg_loss = losses.mean()

    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    if rsi > 70:
        return f"RSI {rsi:.1f}: SELL (Overbought)", rsi
    elif rsi < 30:
        return f"RSI {rsi:.1f}: BUY (Oversold)", rsi
    else:
        return f"RSI {rsi:.1f}: HOLD (Neutral)", rsi


def analyze_ema(stock_symbol):
    stock = yf.Ticker(stock_symbol)
    prices = stock.history(period="6mo")['Close']
    if prices.empty:
        return "No data", None

    ema12 = prices.ewm(span=12, adjust=False).mean().iloc[-1]
    ema26 = prices.ewm(span=26, adjust=False).mean().iloc[-1]

    if ema12 > ema26:
        return f"EMA12 {ema12:.2f} > EMA26 {ema26:.2f}: BUY (Golden Cross)", (ema12, ema26)
    elif ema12 < ema26:
        return f"EMA12 {ema12:.2f} < EMA26 {ema26:.2f}: SELL (Death Cross)", (ema12, ema26)
    else:
        return f"EMA12 {ema12:.2f} = EMA26 {ema26:.2f}: HOLD", (ema12, ema26)


def analyze_macd(stock_symbol):
    stock = yf.Ticker(stock_symbol)
    prices = stock.history(period="6mo")['Close']
    if prices.empty:
        return "No data", None

    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    latest_macd, latest_signal = macd.iloc[-1], signal.iloc[-1]

    if latest_macd > latest_signal:
        return f"MACD {latest_macd:.2f} > Signal {latest_signal:.2f}: BUY", (latest_macd, latest_signal)
    elif latest_macd < latest_signal:
        return f"MACD {latest_macd:.2f} < Signal {latest_signal:.2f}: SELL", (latest_macd, latest_signal)
    else:
        return f"MACD {latest_macd:.2f} = Signal {latest_signal:.2f}: HOLD", (latest_macd, latest_signal)
