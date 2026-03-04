from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

class ICICISlicingScalperFixed(Strategy):
    entry_diff = 0.25      # Buy a slice every time price drops ₹0.25 from peak
    profit_diff = 0.50     # Target profit of ₹0.50 above AVERAGE price
    max_open_qty = 240     
    slicing_qty = 60       

    def init(self):
        self.current_peak = 0

    def next(self):
        price = self.data.Close[-1]
        high = self.data.High[-1]

        # 1. PEAK TRACKING
        if high > self.current_peak:
            self.current_peak = high

        # 2. SLICING ENTRY LOGIC
        if self.position.size < self.max_open_qty:
            if price <= (self.current_peak - self.entry_diff):
                self.buy(size=self.slicing_qty)
                self.current_peak = price 
        
        # 3. FIXED EXIT LOGIC
        if self.position.size > 0:
            # Correct way to get the average entry price of the current position
            # We iterate through all open trades in the position to find the mean
            avg_entry_price = sum(t.entry_price * t.size for t in self.trades) / self.position.size
            
            if price >= (avg_entry_price + self.profit_diff):
                self.position.close()
                self.current_peak = 0