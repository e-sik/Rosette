import os
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import crossover

def SMA(val, period):
    return pd.Series(val).rolling(period).mean()

class SmaCross(Strategy):
    n1 = 10
    n2 = 20

    def init(self):
        # Precompute the two moving averages
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell()

def test_backtest_dataset(data_path):
    print(f"Loading data from {data_path}...")
    ext = os.path.splitext(data_path)[1].lower()
    if ext == '.parquet':
        df = pd.read_parquet(data_path)
        if df.index.name and df.index.name.lower() in ['date', 'time', 'datetime', 'timestamp']:
            df = df.reset_index()
    else:
        df = pd.read_csv(data_path)
    
    df.columns = df.columns.str.strip()
    col_map = {c.lower(): c.capitalize() for c in df.columns}
    df.rename(columns=col_map, inplace=True)
    
    dt_col = next((c for c in df.columns if c.lower() in ['date', 'time', 'datetime', 'timestamp']), None)
    if dt_col:
        df[dt_col] = pd.to_datetime(df[dt_col], format='mixed')
        df.set_index(dt_col, inplace=True)
        df.sort_index(inplace=True)

    print("Running backtest...")
    bt = Backtest(df, SmaCross, commission=.002, exclusive_orders=True)
    stats = bt.run()
    print("Backtest results:")
    print(stats)
    return stats

if __name__ == '__main__':
    data_dir = r"e:\AI\Trade\Antigravity\data"
    parquet_file = os.path.join(data_dir, "MC_3BBLACKBIO_1m.parquet")
    csv_file = os.path.join(data_dir, "MC_ANTHEM_1m.csv")
    
    target_file = parquet_file if os.path.exists(parquet_file) else csv_file
    if os.path.exists(target_file):
        test_backtest_dataset(target_file)
    else:
        print(f"Error: Could not find target file {target_file}")
