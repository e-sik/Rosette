from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

class TataSteelScalperTP(Strategy):
    entry_diff = 0.31
    profit_diff = 0.81
    slicing_qty = 100
    max_qty = 200

    def init(self):
        self.current_peak = 0
        self.last_buy_price = 0

    def next(self):
        # 1. PEAK TRACKING
        # Always track the highest price seen to calculate the entry dip
        price_high = self.data.High[-1]
        price_low = self.data.Low[-1]
        
        if self.current_peak == 0 or price_high > self.current_peak:
            self.current_peak = price_high

        # 2. ENTRY & TP LOGIC
        # Calculate where we want to enter
        entry_signal = self.current_peak - self.entry_diff
        
        # Only place an order if we haven't reached max quantity
        if self.position.size < self.max_qty:
            
            # Calculate the Take Profit price based on the entry level
            tp_level = entry_signal + self.profit_diff
            
            # We place a LIMIT order for entry.
            # We attach the 'tp' parameter immediately.
            # The broker will now handle the exit automatically.
            self.buy(
                size=self.slicing_qty, 
                limit=entry_signal, 
                tp=tp_level
            )
            
            # Update tracking variables
            self.last_buy_price = entry_signal
            # Reset peak to the entry level to start the next dip calculation
            self.current_peak = entry_signal 

        # NOTE: No manual exit code is needed here anymore! 
        # Backtesting.py handles the TP 'limit' sell internally.