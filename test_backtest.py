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

def test_backtest_with_csv(csv_path):
    print(f"Loading data from {csv_path}...")
    # Load DataFrame
    df = pd.read_csv(csv_path)
    
    # Needs a DateTime index
    df['datetime'] = pd.to_datetime(df['datetime'])
    df.set_index('datetime', inplace=True)
    
    # Capitalize the columns needed by Backtesting.py
    df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)

    print("Running backtest...")
    bt = Backtest(df, SmaCross, commission=.002, exclusive_orders=True)
    stats = bt.run()
    print("Backtest results:")
    print(stats)
    return stats

if __name__ == '__main__':
    data_dir = r"e:\AI\Trade\Antigravity\data"
    csv_file = os.path.join(data_dir, "SBIN_NSE_in_daily.csv")
    if os.path.exists(csv_file):
        test_backtest_with_csv(csv_file)
    else:
        print(f"Error: Could not find {csv_file}")
