# Algorithmic Trading Backtester Workspace

A comprehensive Python-based workspace designed to quickly fetch historical market data, easily write diverse trading strategies, and execute lightning-fast backtests with a rich graphical user interface.

## 🚀 Features

* **Historical Data Fetching**: Seamlessly connect to and download daily/intraday bars directly from TradingView without needing login tokens using `tvDatafeed`.
* **Integrated Streamlit UI**: A clean, single-page web dashboard (`app.py`) to manage your data, strategies, and test results.
* **Strategy Editor**: Build custom Python functions extending `backtesting.Strategy` directly in your browser.
* **Execution Override**: Use the advanced UI block to dynamically test parameters and change strategy conditions on-the-fly (`bt.optimize()`).
* **Date Slicing**: Automatically detect Date columns in your data and slice the execution to specific timeframes natively in the UI.
* **Result Comparison**: Natively compare and visually analyze saved historical runs side-by-side.
* **Interactive Charting**: Implements interactive `Bokeh` web charts overlaid with your trades, returns, indicators, and volume straight in the browser. 

## 📁 Project Structure

```text
e:\AI\Trade\Antigravity\
├── app.py                # Main Streamlit Dashboard Application
├── fetch_data.py         # Standalone logic used to connect and pull TVData 
├── test_backtest.py      # A small functional test to verify dependencies 
├── data/                 # Store all fetched historical ticker `.csv` datasets
├── strategies/           # Directory where your custom `.py` strategies are saved
├── results/              # Directory where execution stats and HTML charts are automatically exported
└── refernce/             # User's provided reference codes & Jupyter notebooks (Do Not Delete)
```

## 💻 Getting Started

### 1. Requirements

Ensure you have the required libraries installed in your Python environment. You can install everything you need using the system terminal.
```bash
pip install streamlit backtesting pandas bokeh git+https://github.com/rongardF/tvdatafeed.git
```

### 2. Launch the Application

The entire workflow is driven via the browser dashboard. Once your environment is active, start the Streamlit server using python:

```bash
cd e:\AI\Trade\Antigravity
python -m streamlit run app.py
```

### 3. Usage Guide

1. **Fetch Data (`Tab 1`)**: Open the UI. Specify your target Symbol (e.g. `SBIN`), Exchange (`NSE`), Interval, and depth. This will download a `.csv` file into the `data/` folder.
2. **Strategy Editor (`Tab 2`)**: Write a Python class representing your algorithm extending from `backtesting.Strategy`. Once you save it, it will be placed in the `strategies/` directory.
   - Example strategies use `self.I()` to wrap technical indicators (like Simple Moving Averages). Check the injected default script.
3. **Run Backtest (`Tab 3`)**: Open the execution page. Mix and match any Dataset with any Strategy. 
   - **Date Slicer**: If a dataset has valid timestamps, a calendar view will appear allowing you to trim the backtest to a specific period.
   - **Configure Parameters**: Expand the settings to simulate leverage (`Margin`), capital (`Initial Cash`), spreads, commission sizing, and order locking.
   - **Execution Script**: Optionally override the testing logic if you want to perform heavy optimization grids rather than single tests!
4. **Compare Results (`Tab 4`)**: Review your saved historical executions.
   - Select multiple past runs using the multi-selector to view their performance metrics side-by-side in a comparative table.
   - Select an individual run to render its saved interactive HTML chart natively within the dashboard.
5. **Bulk Testing (`Tab 5`)**: Automatically evaluate a strategy across hundreds of discrete timeframes.
   - Use the **DateTime Mask** to precisely limit the dataset, then select a grouping rule (`Daily`, `Weekly`, `Monthly`, or custom `Intraday Time Windows`).
   - The engine automatically isolates the data, runs an independent backtest on each slice, and ranks the most profitable slices in a unified matrix.
   - Final matrices are automatically saved explicitly to the `bulk_results/` directory.
6. **Optimize Parameters (`Tab 6`)**: Automatically dial in your strategy variables.
   - Select a Strategy, and the engine detects its variables (e.g., SMA periods). Set `Min`, `Max`, and `Step` ranges for each configuration.
   - Restrict your optimization to localized timeframes using the embedded **DateTime Mask**.
   - Choose between **Grid Search (Brute Force)** to systematically test every single combination, or **SMBO (Machine Learning via scikit-optimize/sambo)** to intelligently dial-in variables extremely fast.
   - Winning parameters, grids, and rendering charts are saved to an isolated `opt_results/` directory to prevent clogging your normal backtest results folder.

Every test automatically generates a `_stats.csv` and interactive `_plot.html` inside the `results/` folder for historical record-keeping.

## 🔮 Future Development Guidelines

For further expansion, consider incorporating these features using the provided scaffolding:

- **Expand Data Sources**: Enhance `fetch_data.py` to optionally pull `.csv` sets from alternatives like Yahoo Finance (`yfinance`) or active brokers (Alpaca / Interactive Brokers).
- **In-App Optimization Charts**: Extract the Heatmap functions contained inside the `refernce/d2_optimization.ipynb` sample to render optimization surfaces natively within the Streamlit dashboard on Tab 3.
- **Paper Trading Engine**: Instead of strictly `backtesting`, bind the strategy interface to WebSockets to deploy live alerts.
