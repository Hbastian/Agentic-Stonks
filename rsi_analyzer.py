# simple_stock_advisor.py
import yfinance as yf

print("=== SMART STOCK ADVISOR ===")
print("Helping you make better investment decisions!")
print()

def simple_stock_check(stock_symbol):
    """
    This analyzes stock health using RSI to give investment recommendations
    """
    print(f"Analyzing {stock_symbol}...")
    
    try:
        # Get stock price history
        stock = yf.Ticker(stock_symbol)
        price_history = stock.history(period="3mo")
        
        if price_history.empty:
            print(f"   Could not find data for {stock_symbol}. Please check the symbol.")
            return None
        
        # Get current price and data points
        prices = price_history['Close']
        current_price = prices.iloc[-1]
        
        print(f"   Current Price: ${current_price:.2f}")
        print(f"   Data Period: {len(prices)} trading days")
        
        # Calculate RSI (Relative Strength Index)
        price_changes = []
        for i in range(1, len(prices)):
            change = prices.iloc[i] - prices.iloc[i-1]
            price_changes.append(change)
        
        # Separate gaining days from losing days
        gaining_days = [change for change in price_changes if change > 0]
        losing_days = [change for change in price_changes if change < 0]
        
        if len(gaining_days) == 0 or len(losing_days) == 0:
            print("   Still gathering data on this stock...")
            return None
        
        # Calculate average gains and losses
        avg_gains = sum(gaining_days) / len(gaining_days)
        avg_losses = abs(sum(losing_days) / len(losing_days))
        
        # Calculate RSI score
        if avg_losses == 0:
            rsi_score = 100
        else:
            strength_ratio = avg_gains / avg_losses
            rsi_score = 100 - (100 / (1 + strength_ratio))
        
        print(f"   RSI Health Score: {rsi_score:.1f}/100")
        
        # Generate investment recommendation
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

print("HOW THIS ANALYSIS WORKS:")
print("- Uses RSI (Relative Strength Index) to measure stock momentum")
print("- Scores range from 0-100 with clear investment signals")
print("- Based on 3 months of actual market data")
print()

print("READY TO ANALYZE STOCKS!")
print("=" * 40)

# Analyze popular stocks
stocks_to_analyze = ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN", "NFLX"]

for stock in stocks_to_analyze:
    simple_stock_check(stock)

print()
print("ANALYSIS COMPLETE!")
