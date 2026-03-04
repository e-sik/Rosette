import sys
import os
import time
import json
import argparse
import datetime
import traceback
import pandas as pd
from tvDatafeed import Interval
from fetch_data import fetch_data_hub

# We must ensure we can import load_strategy from app or re-implement it briefly here
# Since app.py might have streamlit dependencies that don't play well when imported in a background pure-python script,
# we will re-implement the simple strategy loader here.
import importlib.util
import inspect
from backtesting import Strategy, Backtest

def load_strategy_from_file(filepath):
    spec = importlib.util.spec_from_file_location("strategy_module", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, Strategy) and obj is not Strategy:
            return obj
    return None

def run_daemon(source, symbol, exchange, interval, strategy_file, init_cash, commission, poll_delay):
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    
    state_file = os.path.join(results_dir, f"pt_state_{symbol}.json")
    stop_file = os.path.join(results_dir, f"pt_stop_{symbol}.txt")
    
    # Clear old stop file if exists
    if os.path.exists(stop_file):
        os.remove(stop_file)
        
    def write_state(data):
        data['last_updated'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=4)

    # Initial state
    state = {
        "status": "Starting",
        "symbol": symbol,
        "strategy": os.path.basename(strategy_file),
        "error": None,
        "metrics": None,
        "recent_trades": []
    }
    write_state(state)
    
    strat_class = load_strategy_from_file(strategy_file)
    if not strat_class:
        state["status"] = "Error"
        state["error"] = "Could not load Strategy class from file."
        write_state(state)
        return

    # Parse interval enum
    interval_tv_enum = None
    interval_yf_str = None
    if source == "TradingView":
        interval_tv_enum = getattr(Interval, interval)
    else:
        interval_yf_str = interval

    print(f"Starting Paper Trading Daemon for {symbol} on {source}...")
    
    last_plot_time = 0
    plot_interval_seconds = 60
    
    while True:
        if os.path.exists(stop_file):
            print(f"Stop file found for {symbol}. Exiting daemon.")
            state["status"] = "Stopped"
            write_state(state)
            os.remove(stop_file)
            break
            
        try:
            state["status"] = "Running"
            
            # Fetch last 30 days
            start_fetch = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
            end_fetch = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            
            filepath, err_msg = fetch_data_hub(source, symbol, exchange, interval_tv_enum, interval_yf_str, start_date=start_fetch, end_date=end_fetch)
            
            if filepath and os.path.exists(filepath):
                df = pd.read_csv(filepath)
                df.columns = df.columns.str.strip()
                col_map = {c.lower(): c.capitalize() for c in df.columns}
                df.rename(columns=col_map, inplace=True)
                if 'Volume' not in df.columns and 'volume' in col_map: 
                    df.rename(columns={'volume': 'Volume'}, inplace=True)
                
                dt_col = next((col for col in df.columns if col.lower() in ['date', 'time', 'datetime', 'timestamp']), None)
                if dt_col:
                    df[dt_col] = pd.to_datetime(df[dt_col], format='mixed')
                    df.set_index(dt_col, inplace=True)
                    df.sort_index(inplace=True)
                    
                    bt = Backtest(
                        df, 
                        strat_class, 
                        cash=init_cash,
                        commission=commission,
                        exclusive_orders=True
                    )
                    stats = bt.run()
                    
                    last_price = float(df['Close'].iloc[-1])
                    last_time = df.index[-1].strftime('%Y-%m-%d %H:%M')
                    curr_equity = float(stats['Equity Final [$]'])
                    return_pct = float(stats['Return [%]'])
                    trades = stats.get('_trades', pd.DataFrame())
                    
                    open_pos = "FLAT"
                    pos_info = "None"
                    if not trades.empty:
                        last_trade = trades.iloc[-1]
                        if pd.isna(last_trade.get('ExitTime')):
                            size = float(last_trade['Size'])
                            entry = float(last_trade['EntryPrice'])
                            open_pos = "LONG" if size > 0 else "SHORT"
                            pnl = float((last_price - entry) * size)
                            pos_info = f"{abs(size)} @ ${entry:.2f} (Live PnL: ${pnl:.2f})"

                    # Throttle HTML plotting to once every 60 seconds
                    current_time = time.time()
                    if (current_time - last_plot_time) > plot_interval_seconds:
                        try:
                            plot_file = os.path.join(results_dir, f"pt_plot_{symbol}.html")
                            bt.plot(filename=plot_file, open_browser=False)
                            last_plot_time = current_time
                        except Exception as plot_err:
                            print(f"Failed to generate plot: {plot_err}")

                    state["metrics"] = {
                        "last_price": last_price,
                        "last_time": last_time,
                        "curr_equity": curr_equity,
                        "return_pct": return_pct,
                        "open_pos": open_pos,
                        "pos_info": pos_info
                    }
                    
                    if not trades.empty:
                        # Convert last 10 trades to dict
                        recent_df = trades.tail(10).iloc[::-1].copy()
                        # Clean all objects to strings for JSON safety
                        for col in recent_df.columns:
                            recent_df[col] = recent_df[col].astype(str)
                        state["recent_trades"] = recent_df.fillna("").to_dict(orient="records")
                    else:
                        state["recent_trades"] = []
                        
                    state["error"] = None
                else:
                    state["error"] = "No Datetime column found in fetched data."
            else:
                state["error"] = f"Fetch failed: {err_msg}"
                
        except Exception as e:
            err_trace = traceback.format_exc()
            print(f"Error in daemon: {err_trace}")
            state["status"] = "Error"
            state["error"] = str(e)
            
        write_state(state)
        time.sleep(poll_delay)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange", required=True)
    parser.add_argument("--interval", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--cash", type=float, required=True)
    parser.add_argument("--commission", type=float, required=True)
    parser.add_argument("--delay", type=int, required=True)
    
    args = parser.parse_args()
    
    # Run the daemon
    run_daemon(
        args.source,
        args.symbol,
        args.exchange,
        args.interval,
        args.strategy,
        args.cash,
        args.commission,
        args.delay
    )
