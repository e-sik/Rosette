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

# Cache TvDatafeed client globally to prevent rate limits inside the background daemons
_TV_CLIENT = None

def fetch_tradingview(symbol, exchange, interval_enum, start_date=None, end_date=None):
    """Fetches maximum data from TradingView and slices locally saving to CSV."""
    global _TV_CLIENT
    
    if _TV_CLIENT is None:
        logger.info(f"Initializing global TvDatafeed client...")
        try:
            _TV_CLIENT = TvDatafeed()
        except Exception as e:
            err = f"Failed to initialize Global TvDatafeed: {e}"
            logger.error(err)
            return None, err
            
    max_bars = 50000
    logger.info(f"Fetching max payload ({max_bars} bars) for {exchange}:{symbol} at {interval_enum.name} interval...")
    try:
        df = _TV_CLIENT.get_hist(symbol=symbol, exchange=exchange, interval=interval_enum, n_bars=max_bars)
    except Exception as e:
        logger.error(f"Network exception during fetch: {e}")
        return None, str(e)
    
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

def fetch_moneycontrol(symbol, interval_str, start_date=None, end_date=None):
    """Fetches historical and intraday data from Moneycontrol's technical charting API."""
    logger.info(f"Fetching {symbol} from Moneycontrol with {interval_str} interval...")
    import requests
    import re
    import datetime

    # 1. Resolve Symbol (Ticker or Index sc_id)
    url_suggest = "https://www.moneycontrol.com/mccode/common/autosuggestion_solr.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": "https://www.moneycontrol.com",
        "Referer": "https://www.moneycontrol.com/",
    }

    sym = symbol.strip().upper()
    if sym.endswith(".NS") or sym.endswith(".BO"):
        sym = sym[:-3]

    INDEX_MAP = {
        "NIFTY": "9",
        "NIFTY50": "9",
        "NIFTY 50": "9",
        "NIFTY_50": "9",
        "SENSEX": "4",
        "BSESN": "4",
        "BSE SENSEX": "4",
        "BANKNIFTY": "23",
        "NIFTYBANK": "23",
        "NIFTY BANK": "23",
    }

    resolved_symbol = sym
    is_index = False

    if sym in INDEX_MAP:
        resolved_symbol = INDEX_MAP[sym]
        is_index = True
    else:
        # Search autosuggest to resolve indices and clean stock symbols
        try:
            suggest_resp = requests.get(url_suggest, params={"query": sym, "type": "1", "format": "json"}, headers=headers, timeout=5)
            if suggest_resp.status_code == 200:
                suggest_data = suggest_resp.json()
                if suggest_data and isinstance(suggest_data, list):
                    for match in suggest_data:
                        link_src = match.get("link_src", "")
                        sc_id = match.get("sc_id", "")
                        
                        # Skip US/Global markets as they are not supported on the Indian charting API
                        if "/us-markets/" in link_src:
                            continue
                            
                        if "/indian-indices/" in link_src:
                            resolved_symbol = sc_id
                            is_index = True
                            logger.info(f"Resolved index '{symbol}' to sc_id '{sc_id}'")
                            break
                        elif "/stockpricequote/" in link_src:
                            # Extract ticker from span inside pdt_dis_nm
                            pdt_dis_nm = match.get("pdt_dis_nm", "")
                            span_match = re.search(r"<span>(.*?)</span>", pdt_dis_nm)
                            if span_match:
                                parts = [p.strip() for p in span_match.group(1).split(",")]
                                if len(parts) >= 2:
                                    resolved_symbol = parts[1]
                                    logger.info(f"Resolved stock '{symbol}' to ticker '{resolved_symbol}'")
                                    break
        except Exception as e:
            logger.error(f"Error during Moneycontrol symbol resolution: {e}")

    # 2. Map Interval String to Moneycontrol Resolutions
    # yfinance uses '1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo'
    interval_map = {
        "1m": "1",
        "2m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "60m": "60",
        "90m": "60",
        "1h": "60",
        "1d": "1D",
        "5d": "1D",
        "1wk": "1W",
        "1mo": "1M",
        "3mo": "1M",
    }
    resolution = interval_map.get(interval_str, "1D")

    # 3. Calculate Date Range and countback
    end_date_dt = pd.to_datetime(end_date) if end_date else pd.to_datetime('today')
    # If daily or weekly, add a day to make sure end date is inclusive
    if resolution in ["1D", "1W", "1M"]:
        end_date_dt = end_date_dt + pd.Timedelta(days=1)
    
    start_date_dt = pd.to_datetime(start_date) if start_date else end_date_dt - pd.Timedelta(days=30)
    
    days_diff = (end_date_dt - start_date_dt).days

    if resolution == "1D":
        countback = days_diff + 10
    elif resolution == "1W":
        countback = (days_diff // 7) + 5
    elif resolution == "1M":
        countback = (days_diff // 30) + 2
    elif resolution == "1":
        countback = (days_diff + 1) * 375
    elif resolution == "3":
        countback = (days_diff + 1) * 125
    elif resolution == "5":
        countback = (days_diff + 1) * 75
    elif resolution == "15":
        countback = (days_diff + 1) * 25
    elif resolution == "30":
        countback = (days_diff + 1) * 13
    elif resolution == "60":
        countback = (days_diff + 1) * 7
    else:
        countback = days_diff + 10

    # Cap countback based on verified limits
    if resolution in ["1D", "1W", "1M"]:
        countback = min(max(countback, 2), 10000)
    else:
        countback = min(max(countback, 2), 95000)

    # 4. Request from API
    url_history = "https://priceapi.moneycontrol.com/techCharts/indianMarket/stock/history"
    params = {
        "symbol": resolved_symbol,
        "resolution": resolution,
        "from": str(int(start_date_dt.timestamp())),
        "to": str(int(end_date_dt.timestamp())),
        "countback": str(countback)
    }

    try:
        logger.info(f"Querying Moneycontrol history endpoint with resolved_symbol={resolved_symbol}, resolution={resolution}, countback={countback}...")
        resp = requests.get(url_history, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            err = f"Failed to fetch from Moneycontrol API: HTTP {resp.status_code}"
            logger.error(err)
            return None, err
            
        res_json = resp.json()
        if res_json.get('s') != 'ok':
            err = f"Moneycontrol API error: {res_json.get('errmsg', 'No data returned')}"
            logger.error(err)
            return None, err
            
        # Parse into DataFrame
        df_new = pd.DataFrame({
            'Datetime': pd.to_datetime(res_json['t'], unit='s'),
            'Open': res_json['o'],
            'High': res_json['h'],
            'Low': res_json['l'],
            'Close': res_json['c'],
            'Volume': res_json['v']
        })
        df_new.set_index('Datetime', inplace=True)
        # Match standard yfinance timezone format (localized to UTC)
        df_new.index = df_new.index.tz_localize('UTC')

    except Exception as e:
        err = f"Network or parsing exception: {e}"
        logger.error(err)
        return None, err

    # 5. Fetch & Merge with existing local CSV file (if exists)
    filename = f"MC_{sym}_{interval_str}.csv"
    filepath = os.path.join(DATA_DIR, filename)

    if os.path.exists(filepath):
        try:
            logger.info(f"Existing file found at {filepath}. Merging new data...")
            df_existing = pd.read_csv(filepath, index_col=0, parse_dates=True)
            
            # Combine and deduplicate keeping the latest records
            df_combined = pd.concat([df_existing, df_new])
            df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
            df_combined.sort_index(inplace=True)
            df_new = df_combined
            logger.info(f"Merge successful. Combined row count: {len(df_combined)}")
        except Exception as e:
            logger.error(f"Failed to merge with existing CSV: {e}. Overwriting instead.")

    # 6. Slice local dataframe to matching range
    try:
        sd = pd.to_datetime(start_date).tz_localize('UTC') if start_date else None
        ed = (pd.to_datetime(end_date) + pd.Timedelta(days=1)).tz_localize('UTC') if end_date else None
        
        if sd:
            df_new = df_new.loc[df_new.index >= sd]
        if ed:
            df_new = df_new.loc[df_new.index <= ed]
    except Exception as e:
        logger.error(f"Failed to slice DataFrame by date range: {e}")

    # Set column names and index name
    df_new.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if resolution in ["1D", "1W", "1M"]:
        try:
            df_new.index = df_new.index.date
        except Exception:
            pass
        df_new.index.name = "Date"
    else:
        df_new.index.name = "Datetime"

    # Save to file
    df_new.to_csv(filepath)
    logger.info(f"Successfully saved {len(df_new)} rows to {filepath}")
    return filepath, None

def fetch_data_hub(source, symbol, exchange, interval_tv_enum, interval_yf_str, start_date=None, end_date=None):
    """Routes the fetch request to the proper service."""
    if source == "TradingView":
        return fetch_tradingview(symbol, exchange, interval_tv_enum, start_date, end_date)
    elif source == "Yahoo Finance":
        return fetch_yfinance(symbol, interval_yf_str, start_date, end_date)
    elif source == "Moneycontrol":
        return fetch_moneycontrol(symbol, interval_yf_str, start_date, end_date)
    return None, "Invalid data source selected."

def update_benchmark_data(latest_test_date=None, force=False):
    """Automatically updates the benchmark_nifty50.csv file if it doesn't exist,
    is older than 24 hours, or if the latest test data date exceeds the benchmark's latest date."""
    benchmark_path = os.path.join(DATA_DIR, "benchmark_nifty50.csv")
    
    # Check if we need to update
    should_update = force or not os.path.exists(benchmark_path)
    if not should_update:
        try:
            # Check if latest test date is newer than the benchmark data max date
            if latest_test_date is not None:
                bm_df = pd.read_csv(benchmark_path, index_col=0, parse_dates=True)
                bm_max = pd.to_datetime(bm_df.index.max()).tz_localize(None)
                test_max = pd.to_datetime(latest_test_date).tz_localize(None)
                if test_max > bm_max:
                    should_update = True
                    logger.info(f"Benchmark update required: Test data goes up to {test_max.date()}, but benchmark only goes up to {bm_max.date()}.")
            
            if not should_update:
                mtime = os.path.getmtime(benchmark_path)
                from datetime import datetime
                if (datetime.now() - datetime.fromtimestamp(mtime)).total_seconds() > 86400: # 24 hours
                    should_update = True
        except Exception:
            should_update = True
            
    if should_update:
        logger.info("Benchmark data (benchmark_nifty50.csv) is missing or outdated. Updating from Moneycontrol...")
        from datetime import date
        today_str = str(date.today())
        # Fetch from 2010-01-01 to today
        filepath, err = fetch_moneycontrol("NIFTY 50", "1d", "2010-01-01", today_str)
        if filepath and os.path.exists(filepath):
            try:
                import shutil
                shutil.copy2(filepath, benchmark_path)
                logger.info(f"Successfully updated benchmark file: {benchmark_path}")
                return True, None
            except Exception as copy_err:
                err_msg = f"Failed to copy benchmark file: {copy_err}"
                logger.error(err_msg)
                return False, err_msg
        else:
            err_msg = f"Failed to fetch benchmark from Moneycontrol: {err}"
            logger.error(err_msg)
            return False, err_msg
    return True, None

if __name__ == "__main__":
    fetch_and_save_data('SBIN', 'NSE', Interval.in_daily, 2000)
    fetch_and_save_data('GOOG', 'NASDAQ', Interval.in_daily, 2000)
