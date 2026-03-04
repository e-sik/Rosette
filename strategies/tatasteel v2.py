from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

class ICICIScalperFinal(Strategy):
    entry_diff = 0.25
    profit_diff = 0.75
    max_open_qty = 200
    slicing_qty = 100

    def init(self):
        self.current_peak = 0

    def next(self):
        price = self.data.Close[-1]
        high = self.data.High[-1]

        # 1. PEAK TRACKING
        if high > self.current_peak or self.current_peak == 0:
            self.current_peak = high

        # 2. ENTRY LOGIC (Scaling In)
        # Check if total current size < max allowed
        if self.position.size < self.max_open_qty:
            if price <= (self.current_peak - self.entry_diff):
                # We place a new buy order without closing existing trades
                self.buy(size=self.slicing_qty)
                self.current_peak = price # Local reset to allow next slice

        # 3. EXIT LOGIC (Average Price Close)
        if self.position.size > 0:
            # Weighted Average Price of ALL open trades
            avg_entry = sum(t.entry_price * t.size for t in self.trades) / self.position.size
            
            if price >= (avg_entry + self.profit_diff):
                self.position.close()
                self.current_peak = 0 # FULL RESET to find new morning high