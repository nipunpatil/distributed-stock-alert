import yfinance as yf
stock = yf.Ticker("AAPL")
price = stock.info.get('currentPrice')
print(price)
stock1 = yf.Ticker("GOOG")
price = stock1.info.get('currentPrice')
print(price)