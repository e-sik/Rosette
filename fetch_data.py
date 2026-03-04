import os
import logging
import pandas as pd
from tvDatafeed import TvDatafeed, Interval

# Configure paths
DATA_DIR = r"e:\AI\Trade\Antigravity\data"
LOG_DIR = "application-logs"

# Ensure log dir exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Set up module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler(os.path.join(LOG_DIR, "app.log"))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(fh)

def fetch_tradingview(symbol, exchange, interval_enum, start_date=None, end_date=None):
    """Fetches maximum data from TradingView and slices locally saving to CSV."""
    logger.info(f"Initializing TvDatafeed for {symbol}")
    tv = TvDatafeed()
    
    max_bars = 50000
    logger.info(f"Fetching max payload ({max_bars} bars) for {exchange}:{symbol} at {interval_enum.name} interval...")
    df = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval_enum, n_bars=max_bars)
    
    if df is None or df.empty:
        err = f"Failed to fetch data for {symbol} via TradingView."
        logger.error(err)
        return None, err
        
    try:
        if start_date:
            df = df.loc[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df.loc[df.index <= pd.to_datetime(end_date)]
    except Exception as e:
        logger.error(f"Failed to slice data by date: {e}")
        
    logger.info(f"Successfully processed {len(df)} rows within range.")
    
    filename = f"TV_{symbol}_{exchange}_{interval_enum.name}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    df.to_csv(filepath)
    return filepath, None

def fetch_yfinance(symbol, interval_str, start_date=None, end_date=None):
    """Fetches data from Yahoo Finance."""
    logger.info(f"Fetching {symbol} from yfinance with {interval_str} interval...")
    import yfinance as yf
    
    # yfinance uses '1m', '5m', '1h', '1d', '1wk', '1mo'
    # Valid intervals: [1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo]
    
    # Ensure end date is inclusive if we have an end_date string by adding 1 day
    if end_date:
        ed = pd.to_datetime(end_date) + pd.Timedelta(days=1)
        ed_str = ed.strftime('%Y-%m-%d')
    else:
        ed_str = None
        
    df = yf.download(symbol, start=start_date, end=ed_str, interval=interval_str)
    
    if df is None or df.empty:
        err = f"Failed to fetch {symbol} from yfinance. This is usually caused by an invalid ticker (did you forget the .NS suffix?) or by requesting Intraday data ({interval_str}) outside of Yahoo's calendar limits. Note: 1m data is limited to the last 7 days. 5m-90m is limited to 60 days. 1h is limited to 730 days."
        logger.error(err)
        return None, err
        
    # Reset multi-index columns if yf returns them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
        df.columns.name = None
    
    # Capitalize columns to match standard backtesting format
    df.columns = [c.capitalize() for c in df.columns]
    
    filename = f"YF_{symbol}_{interval_str}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    df.to_csv(filepath)
    return filepath, None

def fetch_data_hub(source, symbol, exchange, interval_tv_enum, interval_yf_str, start_date=None, end_date=None):
    """Routes the fetch request to the proper service."""
    if source == "TradingView":
        return fetch_tradingview(symbol, exchange, interval_tv_enum, start_date, end_date)
    elif source == "Yahoo Finance":
        return fetch_yfinance(symbol, interval_yf_str, start_date, end_date)
    return None, "Invalid data source selected."

if __name__ == "__main__":
    fetch_and_save_data('SBIN', 'NSE', Interval.in_daily, 2000)
    fetch_and_save_data('GOOG', 'NASDAQ', Interval.in_daily, 2000)
