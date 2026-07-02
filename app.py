import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import os
import sys
import pandas as pd
import importlib.util
import inspect
import logging
from backtesting import Strategy, Backtest
import backtesting.backtesting as bt_module

class StreamlitTQDM:
    def __init__(self, iterable=None, total=None, desc=None, leave=False, mininterval=2, **kwargs):
        self.iterable = iterable
        if total is not None:
            self.total = total
        elif iterable is not None:
            try:
                self.total = len(iterable)
            except:
                self.total = 0
        else:
            self.total = 0
            
        self.desc = desc or "Executing"
        self.progress_bar = st.progress(0.0)
        self.status_text = st.empty()
        self.n = 0
        self.iterator = iter(self.iterable) if self.iterable is not None else None
        
    def __iter__(self):
        return self
        
    def __next__(self):
        self.update(1)
        if self.iterator is not None:
            try:
                return next(self.iterator)
            except StopIteration:
                self.close()
                raise
        return None
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def update(self, n=1):
        self.n += n
        if self.total > 0:
            frac = min(self.n / self.total, 1.0)
            self.progress_bar.progress(frac)
            self.status_text.write(f"**{self.desc}**: {self.n}/{self.total} completed...")
            
    def close(self):
        try:
            self.progress_bar.empty()
            self.status_text.empty()
        except:
            pass

# Globally patch backtesting's internal tqdm to use Streamlit's progress bar
bt_module._tqdm = StreamlitTQDM

import time
import ast
import traceback
from streamlit_ace import st_ace

# --- Logging Config ---
LOG_DIR = "application-logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def purge_old_files(directories, days=7):
    """Deletes files older than the specified number of days to adhere to free-tier SaaS archival limits."""
    current_time = time.time()
    threshold = days * 86400  # 86400 seconds in a day
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                # Never delete the persistent benchmark dataset
                if filename == "benchmark_nifty50.csv":
                    continue
                # Check last modification time
                if os.path.getmtime(filepath) < (current_time - threshold):
                    try:
                        os.remove(filepath)
                        print(f"Archived/Purged old file: {filepath}")
                    except Exception as e:
                        print(f"Failed to purge {filepath}: {e}")

# Run archival purge on startup across all caching directories (7 days retention)
purge_old_files([LOG_DIR, "data", "results", "opt_results"], days=7)

# Configure the root logger to catch all events, including from imported modules
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Verify log file is active
logger.info("Application initialized. Log file is active.")

# --- Layout Config ---
st.set_page_config(page_title="Rosette | Quantitative Finance", layout="wide", page_icon="assets/rosette_logo.png")

# --- Custom CSS for Professional Layout ---
st.markdown("""
<style>
    /* Compact the main content area — enough room for header to breathe */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; }
    
    /* Elegant top bar */
    .rosette-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.6rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1rem;
    }
    .rosette-header img {
        height: 28px;
        width: 28px;
        border-radius: 6px;
    }
    .rosette-header .title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #fafafa;
        letter-spacing: -0.02em;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    .rosette-header .sep {
        color: rgba(255, 255, 255, 0.15);
        font-size: 1.2rem;
        font-weight: 300;
    }
    .rosette-header .subtitle {
        font-size: 0.8rem;
        color: rgba(255, 255, 255, 0.4);
        font-weight: 400;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    
    /* Tighten tab spacing */
    .stTabs [data-baseweb="tab-list"] { gap: 0px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        font-size: 0.82rem;
        font-weight: 500;
    }
    
    /* Metric cards */
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: rgba(255, 255, 255, 0.5) !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
        font-weight: 600;
    }
    
    /* Expander refinement */
    .streamlit-expanderHeader {
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* Sidebar refinement */
    section[data-testid="stSidebar"] {
        padding-top: 1rem;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.5rem !important;
    }
    
    /* Table/dataframe styling */
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    
    /* Subheader spacing */
    h2 { margin-top: 0.5rem !important; margin-bottom: 0.25rem !important; }
    h3 { margin-top: 0.5rem !important; margin-bottom: 0.25rem !important; }
    
    /* Divider spacing */
    hr { margin: 0.75rem 0 !important; }
    
    /* Sidebar Navigation Circles and Labels */
    section[data-testid="stSidebar"] [data-testid="column"]:first-child button {
        border-radius: 50% !important;
        width: 38px !important;
        height: 38px !important;
        min-width: 38px !important;
        max-width: 38px !important;
        min-height: 38px !important;
        max-height: 38px !important;
        padding: 0 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.1rem !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    /* Secondary (inactive) circle button styling */
    section[data-testid="stSidebar"] [data-testid="column"]:first-child button[data-testid="baseButton-secondary"] {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        color: rgba(255, 255, 255, 0.7) !important;
    }
    section[data-testid="stSidebar"] [data-testid="column"]:first-child button[data-testid="baseButton-secondary"]:hover {
        background-color: rgba(108, 99, 255, 0.15) !important;
        border-color: #6C63FF !important;
        color: #ffffff !important;
        transform: scale(1.08);
    }
    
    /* Primary (active) circle button styling */
    section[data-testid="stSidebar"] [data-testid="column"]:first-child button[data-testid="baseButton-primary"] {
        background-color: #6C63FF !important;
        border: 1px solid #6C63FF !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(108, 99, 255, 0.4) !important;
    }
    section[data-testid="stSidebar"] [data-testid="column"]:first-child button[data-testid="baseButton-primary"]:hover {
        transform: scale(1.08);
        box-shadow: 0 0 16px rgba(108, 99, 255, 0.6) !important;
    }
    
    /* Target second column (text labels) in the sidebar */
    section[data-testid="stSidebar"] [data-testid="column"]:nth-child(2) button {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        text-align: left !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        color: rgba(255, 255, 255, 0.6) !important;
        justify-content: flex-start !important;
        width: 100% !important;
        height: 38px !important;
        transition: all 0.2s ease-in-out !important;
    }
    section[data-testid="stSidebar"] [data-testid="column"]:nth-child(2) button:hover {
        color: #ffffff !important;
        background: transparent !important;
        border: none !important;
    }
    
    /* Style for the active tab's label button */
    section[data-testid="stSidebar"] [data-testid="column"]:nth-child(2) button[data-testid="baseButton-primary"] {
        color: #ffffff !important;
        font-weight: 700 !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Compact Header ---
import base64 as _b64
_logo_b64 = ""
try:
    with open("assets/rosette_logo.png", "rb") as _f:
        _logo_b64 = _b64.b64encode(_f.read()).decode()
except Exception:
    pass

_logo_tag = f'<img src="data:image/png;base64,{_logo_b64}" alt="">' if _logo_b64 else ""
st.markdown(f"""
<div class="rosette-header">
    {_logo_tag}
    <span class="title">Rosette</span>
    <span class="sep">|</span>
    <span class="subtitle">Algorithmic Trading Workspace</span>
</div>
""", unsafe_allow_html=True)

# --- Sidebar ---
try:
    st.sidebar.image("assets/rosette_banner.png", use_container_width=True)
except Exception:
    pass

# Sidebar Workspace Navigation
st.sidebar.markdown("<div style='margin-top: 0.5rem; margin-bottom: 0.8rem; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: rgba(255, 255, 255, 0.4);'>Workspace Navigation</div>", unsafe_allow_html=True)

TABS = ["Fetch Data", "Strategy Editor", "Run Backtest", "Results & Analytics", "Optimize Parameters", "Paper Trading"]
TAB_ICONS = ["📥", "📝", "⚡", "📊", "⚙️", "🧪"]

# Navigation Menu inside Sidebar
for label, icon in zip(TABS, TAB_ICONS):
    col_btn, col_lbl = st.sidebar.columns([1, 4])
    is_active = (st.session_state.get('active_tab', "Fetch Data") == label)
    btn_type = "primary" if is_active else "secondary"
    
    with col_btn:
        if st.button(icon, key=f"nav_btn_{label}", type=btn_type, help=f"Go to {label}"):
            st.session_state['active_tab'] = label
            st.rerun()
            
    with col_lbl:
        if st.button(label, key=f"nav_lbl_{label}", type=btn_type, help=f"Go to {label}"):
            st.session_state['active_tab'] = label
            st.rerun()

st.sidebar.divider()

st.sidebar.header("Control Panel")
if st.session_state.get('bulk_running', False):
    if st.sidebar.button("🛑 STOP BULK TEST", type="primary", use_container_width=True, help="Stop the currently running bulk backtesting loop immediately."):
        with open("stop_flag.txt", "w") as f:
            f.write("stop")
        st.sidebar.warning("Stop signal sent! Waiting for loop to terminate...")

if st.sidebar.button("Stop Server", type="primary", use_container_width=True, help="Click to shut down the Streamlit server. You will need to use your terminal to start it again."):
    st.sidebar.warning("Shutting down the server...")
    logger.info("Server stopped manually via sidebar button.")
    os._exit(0)

st.sidebar.divider()
st.sidebar.info("**Data Archival Policy**\n\nAll Data, Backtest Results, and Charts are automatically pruned after **7 Days** of inactivity.")
st.sidebar.caption("Community Edition")

# --- Initialize Session State ---
if 'active_tab' not in st.session_state:
    st.session_state['active_tab'] = "Fetch Data"
if 'data_fetched' not in st.session_state:
    st.session_state['data_fetched'] = False
if 'ide_theme' not in st.session_state:
    st.session_state['ide_theme'] = 'dracula'
if 'ide_keybinding' not in st.session_state:
    st.session_state['ide_keybinding'] = 'vscode'
if 'ide_font_size' not in st.session_state:
    st.session_state['ide_font_size'] = 14
if 'ide_tab_size' not in st.session_state:
    st.session_state['ide_tab_size'] = 4
if 'ide_wrap_lines' not in st.session_state:
    st.session_state['ide_wrap_lines'] = True
if 'ide_show_gutter' not in st.session_state:
    st.session_state['ide_show_gutter'] = True

# Global fallback for timeframe resampling (avoids NameError in optimization/other tabs)
resample_tf = "No Resampling (Use Native)"

def load_strategy(filepath):
    """Dynamically load the user's strategy file and extract the Strategy class."""
    if "strategy_module" in sys.modules:
        del sys.modules["strategy_module"]
        
    spec = importlib.util.spec_from_file_location("strategy_module", filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules["strategy_module"] = module
    spec.loader.exec_module(module)
    
    # Find classes that inherit from Strategy
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, Strategy) and obj is not Strategy:
            return obj
    return None

# --- Strategy Evaluation & Risk Helpers ---
def calculate_strategy_metrics(stats, trades_df):
    """
    Extracts and calculates the standardized institutional-grade metrics.
    Ensures safe division and formats values properly.
    """
    if stats is None:
        stats = {}
        
    metrics = {}
    
    # 1. Absolute Returns
    metrics['Cumulative Return [%]'] = float(stats.get('Return [%]', 0.0))
    metrics['Annualized Return [%]'] = float(stats.get('Return (Ann.) [%]', 0.0))
    metrics['Final Equity [$]'] = float(stats.get('Equity Final [$]', 0.0))
    
    # 2. Risk & Exposure
    metrics['Max Drawdown [%]'] = float(stats.get('Max. Drawdown [%]', 0.0))
    metrics['Avg Drawdown [%]'] = float(stats.get('Avg. Drawdown [%]', 0.0))
    
    # Max Drawdown Duration could be a Timedelta or string, convert to string
    metrics['Max Drawdown Duration'] = str(stats.get('Max. Drawdown Duration', '0 days'))
    metrics['Exposure Time [%]'] = float(stats.get('Exposure Time [%]', 0.0))
    
    # 3. Risk-Adjusted Ratios
    metrics['Sharpe Ratio'] = float(stats.get('Sharpe Ratio', 0.0))
    if np.isnan(metrics['Sharpe Ratio']) or np.isinf(metrics['Sharpe Ratio']):
        metrics['Sharpe Ratio'] = 0.0
        
    metrics['Sortino Ratio'] = float(stats.get('Sortino Ratio', 0.0))
    if np.isnan(metrics['Sortino Ratio']) or np.isinf(metrics['Sortino Ratio']):
        metrics['Sortino Ratio'] = 0.0
        
    metrics['Calmar Ratio'] = float(stats.get('Calmar Ratio', 0.0))
    if np.isnan(metrics['Calmar Ratio']) or np.isinf(metrics['Calmar Ratio']):
        metrics['Calmar Ratio'] = 0.0
        
    # 4. Trade Efficiency & Statistics
    metrics['Total Trades'] = int(stats.get('# Trades', 0))
    metrics['Win Rate [%]'] = float(stats.get('Win Rate [%]', 0.0))
    
    avg_win = 0.0
    avg_loss = 0.0
    profit_factor = 0.0
    expectancy = 0.0
    
    if trades_df is not None and not trades_df.empty:
        # Standardize column casing
        trades_df.columns = trades_df.columns.str.strip()
        ret_col = next((c for c in trades_df.columns if c.lower() in ['returnpct', 'return_pct', 'return %']), None)
        pnl_col = next((c for c in trades_df.columns if c.lower() in ['pnl', 'p_n_l', 'profit_loss']), None)
        
        metrics['Total Trades'] = len(trades_df)
        
        if ret_col:
            win_trades = trades_df[trades_df[ret_col] > 0]
            loss_trades = trades_df[trades_df[ret_col] < 0]
            
            # Update win rate
            metrics['Win Rate [%]'] = (len(win_trades) / len(trades_df)) * 100.0
            
            avg_win = float(win_trades[ret_col].mean()) if not win_trades.empty else 0.0
            avg_loss = float(abs(loss_trades[ret_col].mean())) if not loss_trades.empty else 0.0
            
            gross_profit = float(win_trades[pnl_col].sum()) if (pnl_col and not win_trades.empty) else 0.0
            gross_loss = float(abs(loss_trades[pnl_col].sum())) if (pnl_col and not loss_trades.empty) else 0.0
            
            if gross_profit == 0.0 and gross_loss == 0.0:
                gross_profit = float(win_trades[ret_col].sum()) if not win_trades.empty else 0.0
                gross_loss = float(abs(loss_trades[ret_col].sum())) if not loss_trades.empty else 0.0
                
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
            
            win_rate = len(win_trades) / len(trades_df)
            loss_rate = len(loss_trades) / len(trades_df)
            expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
            
            is_empty_stats = False
            if stats is None:
                is_empty_stats = True
            elif isinstance(stats, dict):
                is_empty_stats = (len(stats) == 0)
            elif hasattr(stats, 'empty'):
                is_empty_stats = stats.empty

            if is_empty_stats:
                if pnl_col:
                    total_pnl = trades_df[pnl_col].sum()
                    metrics['Cumulative Return [%]'] = total_pnl
    else:
        profit_factor = float(stats.get('Profit Factor', 0.0))
        if np.isnan(profit_factor) or np.isinf(profit_factor):
            profit_factor = 0.0
            
    metrics['Profit Factor'] = profit_factor
    metrics['Avg Win [%]'] = avg_win
    metrics['Avg Loss [%]'] = avg_loss
    metrics['P/L Ratio'] = avg_win / avg_loss if avg_loss > 0 else 0.0
    metrics['Expectancy [%]'] = expectancy
    
    return metrics

def calculate_stock_consolidation(stock_name, stock_trades, init_cash):
    """
    Consolidates backtest metrics for an individual stock across all its trade logs.
    """
    if stock_trades.empty:
        return {
            'Stock': stock_name,
            'Total Trades': 0,
            'Win Rate [%]': 0.0,
            'Profit Factor': 0.0,
            'Total PnL ($)': 0.0,
            'Cumulative Return [%]': 0.0
        }
    
    ret_col = next((c for c in stock_trades.columns if c.lower() in ['returnpct', 'return_pct', 'return %']), None)
    pnl_col = next((c for c in stock_trades.columns if c.lower() in ['pnl', 'p_n_l', 'profit_loss']), None)
    
    total_pnl = float(stock_trades[pnl_col].sum()) if pnl_col else 0.0
    cum_ret = (total_pnl / init_cash) * 100.0 if init_cash > 0 else 0.0
    
    win_trades = stock_trades[stock_trades[ret_col] > 0] if (ret_col and not stock_trades.empty) else pd.DataFrame()
    loss_trades = stock_trades[stock_trades[ret_col] < 0] if (ret_col and not stock_trades.empty) else pd.DataFrame()
    
    win_rate = (len(win_trades) / len(stock_trades)) * 100.0 if not stock_trades.empty else 0.0
    
    gross_profit = float(win_trades[pnl_col].sum()) if (pnl_col and not win_trades.empty) else 0.0
    gross_loss = float(abs(loss_trades[pnl_col].sum())) if (pnl_col and not loss_trades.empty) else 0.0
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    
    return {
        'Stock': stock_name,
        'Total Trades': len(stock_trades),
        'Win Rate [%]': win_rate,
        'Profit Factor': profit_factor,
        'Total PnL ($)': total_pnl,
        'Cumulative Return [%]': cum_ret
    }

def run_monte_carlo_sim(returns, n_simulations=1000, confidence_level=95, start_capital=10000):
    """
    Runs a vectorized Monte Carlo simulation by shuffling returns.
    """
    if len(returns) < 5:
        return None
        
    shuffled_rets = np.random.choice(returns, size=(n_simulations, len(returns)), replace=True)
    compounded = np.cumprod(1 + shuffled_rets, axis=1)
    
    # Insert start capital at the beginning of each curve
    all_curves = np.hstack([np.ones((n_simulations, 1)) * start_capital, start_capital * compounded])
    
    peaks = np.maximum.accumulate(all_curves, axis=1)
    drawdowns = (all_curves - peaks) / peaks
    max_dds = np.min(drawdowns, axis=1) * 100.0  # %
    
    final_vals = all_curves[:, -1]
    
    return {
        'curves': all_curves,
        'max_dds': max_dds,
        'final_vals': final_vals,
        'expected_final_equity': float(np.mean(final_vals)),
        'median_max_drawdown': float(np.median(max_dds)),
        'var_max_drawdown': float(np.percentile(max_dds, 100 - confidence_level))
    }

def get_monte_carlo_verdict(original_dd, median_dd):
    if original_dd is None:
        return "Independent Analysis", "info"
    
    # Make original drawdown negative if it is stored as positive
    orig_dd_neg = -abs(original_dd)
    med_dd_neg = -abs(median_dd)
    
    diff = med_dd_neg - orig_dd_neg  # median - original
    if diff < -5:  # median is much worse (e.g. -25% vs -15%)
        return "Sequence Luck Detected", "warning"
    elif diff > 5:  # median is much better (e.g. -10% vs -20%)
        return "Pessimistic Backtest", "success"
    else:
        return "Statistically Robust", "info"

def render_unified_dashboard(run_name, metrics, trades_df, plot_html_path, mc_results):
    """
    Renders the unified strategy evaluation and risk dashboard in Streamlit.
    """
    st.markdown(f"## Performance & Risk: `{run_name}`")
    
    # 1. Header & Summary Metrics
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    cagr = metrics.get('Annualized Return [%]', 0.0)
    pf = metrics.get('Profit Factor', 0.0)
    max_dd = metrics.get('Max Drawdown [%]', 0.0)
    win_rate = metrics.get('Win Rate [%]', 0.0)
    sortino = metrics.get('Sortino Ratio', 0.0)
    
    orig_dd = metrics.get('Max Drawdown [%]', None)
    median_dd = mc_results.get('median_max_drawdown', 0.0) if mc_results else 0.0
    verdict, verdict_type = get_monte_carlo_verdict(orig_dd, median_dd)
    
    c1.metric("CAGR (Ann. Return)", f"{cagr:.2f}%")
    c2.metric("Profit Factor", f"{pf:.2f}")
    c3.metric("Max Drawdown", f"{max_dd:.2f}%")
    c4.metric("Win Rate", f"{win_rate:.2f}%")
    c5.metric("Sortino Ratio", f"{sortino:.2f}")
    
    with c6:
        st.write("**Monte Carlo Verdict**")
        if verdict_type == "success":
            st.success(verdict)
        elif verdict_type == "warning":
            st.warning(verdict)
        else:
            st.info(verdict)
            
    st.divider()
    
    # 2. Detailed Performance Table
    with st.expander("View Complete Strategy Evaluation Metrics", expanded=False):
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown("**Absolute Performance**")
            st.write(f"- **Cumulative Return:** {metrics.get('Cumulative Return [%]', 0.0):.2f}%")
            st.write(f"- **Annualized Return (CAGR):** {metrics.get('Annualized Return [%]', 0.0):.2f}%")
            st.write(f"- **Final Equity:** ${metrics.get('Final Equity [$]', 0.0):,.2f}")
            
            st.markdown("**Risk-Adjusted Ratios**")
            st.write(f"- **Sharpe Ratio:** {metrics.get('Sharpe Ratio', 0.0):.2f}")
            st.write(f"- **Sortino Ratio:** {metrics.get('Sortino Ratio', 0.0):.2f}")
            st.write(f"- **Calmar Ratio:** {metrics.get('Calmar Ratio', 0.0):.2f}")
            
        with m_col2:
            st.markdown("**Risk & Exposure**")
            st.write(f"- **Max Drawdown:** {metrics.get('Max Drawdown [%]', 0.0):.2f}%")
            st.write(f"- **Average Drawdown:** {metrics.get('Avg Drawdown [%]', 0.0):.2f}%")
            st.write(f"- **Max Drawdown Duration:** {metrics.get('Max Drawdown Duration', 'N/A')}")
            st.write(f"- **Exposure Time (Time in Market):** {metrics.get('Exposure Time [%]', 0.0):.2f}%")
            
            st.markdown("**Trade Statistics**")
            st.write(f"- **Total Trades:** {metrics.get('Total Trades', 0)}")
            st.write(f"- **Win Rate:** {metrics.get('Win Rate [%]', 0.0):.2f}%")
            st.write(f"- **Profit/Loss Ratio:** {metrics.get('P/L Ratio', 0.0):.2f} (Avg Win: {metrics.get('Avg Win [%]', 0.0):.2f}%, Avg Loss: {metrics.get('Avg Loss [%]', 0.0):.2f}%)")
            st.write(f"- **Expectancy per Trade:** {metrics.get('Expectancy [%]', 0.0):.4f}%")
            
    st.divider()
    
    # 3. Monte Carlo Analysis Visualizations
    if mc_results:
        st.subheader("Monte Carlo Risk & Robustness Analysis")
        mc_col1, mc_col2 = st.columns([3, 2])
        
        with mc_col1:
            st.markdown("### Equity Curve 'Spaghetti' Plot")
            st.caption("Showing 50 random simulated paths out of all simulations. The cyan line shows the Average Path.")
            
            n_simulations = len(mc_results['max_dds'])
            all_eq_curves = mc_results['curves']
            sample_indices = np.random.choice(range(n_simulations), min(50, n_simulations), replace=False)
            
            from bokeh.plotting import figure
            from bokeh.models import NumeralTickFormatter
            from bokeh.embed import file_html
            from bokeh.resources import CDN
            
            p_mc = figure(title="Simulated Equity Paths", 
                          x_axis_label='Trade Number', 
                          y_axis_label='Equity ($)',
                          tools="pan,box_zoom,reset,save",
                          active_drag="box_zoom",
                          height=400,
                          sizing_mode="stretch_width")
            
            p_mc.background_fill_color = "#0e1117"
            p_mc.border_fill_color = "#0e1117"
            p_mc.title.text_color = "white"
            p_mc.xaxis.axis_label_text_color = "white"
            p_mc.yaxis.axis_label_text_color = "white"
            p_mc.xaxis.major_label_text_color = "white"
            p_mc.yaxis.major_label_text_color = "white"
            p_mc.grid.grid_line_color = "#333333"
            
            n_points = len(all_eq_curves[0])
            if n_points > 500:
                plot_indices = np.linspace(0, n_points - 1, 500, dtype=int)
            else:
                plot_indices = np.arange(n_points)

            for idx in sample_indices:
                curve = all_eq_curves[idx]
                p_mc.line(list(plot_indices), list(curve[plot_indices] if n_points > 500 else curve), line_width=1, alpha=0.3, color="gray")
                
            avg_curve = np.mean(all_eq_curves, axis=0)
            p_mc.line(list(plot_indices), list(avg_curve[plot_indices] if n_points > 500 else avg_curve), line_width=4, color="#00d4ff", legend_label="Average Path")
            
            p_mc.yaxis.formatter = NumeralTickFormatter(format="$0,0")
            p_mc.legend.location = "top_left"
            p_mc.legend.background_fill_color = "#0e1117"
            p_mc.legend.label_text_color = "white"
            p_mc.legend.background_fill_alpha = 0.8
            
            mc_html = file_html(p_mc, CDN, "Monte Carlo Spaghetti Plot")
            components.html(mc_html, height=430)
            
        with mc_col2:
            st.markdown("### Max Drawdown Distribution")
            st.caption("Probability distribution of worst-case drawdowns across all simulation runs.")
            
            st.metric("Expected Final Equity", f"${mc_results['expected_final_equity']:,.2f}")
            st.metric("Median Simulated Drawdown", f"{mc_results['median_max_drawdown']:.2f}%")
            st.metric("95% Probable Max DD (VaR)", f"{mc_results['var_max_drawdown']:.2f}%")
            
            counts, bin_edges = np.histogram(mc_results['max_dds'], bins=20)
            bin_labels = [f"{x:.1f}%" for x in bin_edges[:-1]]
            hist_df = pd.DataFrame({
                'Count': counts
            }, index=bin_labels)
            
            st.bar_chart(hist_df, use_container_width=True)
            
        st.divider()
        
    # 4. Interactive Historical Chart
    if plot_html_path and os.path.exists(plot_html_path):
        st.subheader("Interactive Backtest Chart")
        with open(plot_html_path, "r", encoding='utf-8') as f:
            html_content = f.read()
            components.html(html_content, height=700, scrolling=True)
        st.divider()
        
    # 5. Detailed Trade Ledger
    if trades_df is not None and not trades_df.empty:
        st.subheader("Trade Ledger")
        st.write(f"Displaying **{len(trades_df)}** trades.")
        
        def highlight_pnl(val):
            try:
                color = 'rgba(0, 255, 0, 0.1)' if float(val) > 0 else 'rgba(255, 0, 0, 0.1)'
                return f'background-color: {color}'
            except:
                return ''
                
        pnl_col = next((c for c in trades_df.columns if c.lower() in ['pnl', 'p_n_l', 'profit_loss']), None)
        if pnl_col and len(trades_df) <= 500:
            st.dataframe(trades_df.style.map(highlight_pnl, subset=[pnl_col]), use_container_width=True)
        else:
            st.dataframe(trades_df, use_container_width=True)

# --- Active Tab Routing ---
active_tab = st.session_state.get('active_tab', "Fetch Data")

# --- TAB 1: Data Fetching ---
if active_tab == "Fetch Data":
    st.header("Fetch Historical Data")
    st.write("Download historical data directly from TradingView, Yahoo Finance, or Moneycontrol.")
    
    st.info("""
    **API Limitations Reminder:**
    * **Yahoo Finance**: Excellent for 10+ years of Daily/Weekly data. Strictly limits `1m` intraday to the last 7 days, and `5m-90m` to the last 60 days.
    * **TradingView**: No specific date limits, but hard-caps the total number of historical candles output to ~5,000 per request.
    * **Moneycontrol**: Excellent for deep intraday data (allows up to 1 year of `1m`/`5m` history in a single request, vs. yfinance's 7/60 day limits). Daily history goes back to 2000. Intraday data older than 1 year is pruned by the server, but the app will automatically **Fetch & Merge** with your local CSV to preserve older history!
    """)
    
    data_source_opt = st.selectbox("Data Source", ["TradingView", "Yahoo Finance", "Moneycontrol"], help="TradingView is great for standard symbols. Yahoo Finance is better for very deep historical backtesting (10+ years). Moneycontrol is best for deep intraday data.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Symbol", value="SBIN").upper()
        if data_source_opt == "Yahoo Finance":
            st.caption("Tip: Add `.NS` for NSE stocks (e.g. SBIN.NS) or `.BO` for BSE.")
        elif data_source_opt == "Moneycontrol":
            st.caption("Tip: Enter standard tickers (e.g. SBIN, RELIANCE) or index names (e.g. NIFTY 50, NIFTY BANK). Suffixes like `.NS` are resolved automatically!")
    with col2:
        exchange = st.text_input("Exchange (TradingView only)", value="NSE").upper()
    with col3:
        if data_source_opt == "TradingView":
            tv_options = ['in_1_minute', 'in_3_minute', 'in_5_minute', 'in_15_minute', 'in_30_minute', 'in_45_minute', 
                          'in_1_hour', 'in_2_hour', 'in_3_hour', 'in_4_hour', 'in_daily', 'in_weekly', 'in_monthly']
            interval_selection = st.selectbox("Interval", tv_options, index=10)
        else:
            yf_options = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']
            interval_selection = st.selectbox("Interval", yf_options, index=8)
        
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_fetch = st.date_input("Start Date", value=pd.to_datetime('2022-01-01').date())
    with col_d2:
        end_date_fetch = st.date_input("End Date", value=pd.to_datetime('today').date())
    
    if data_source_opt == "TradingView":
        st.caption("Note: TradingView limits free history. If your date range exceeds the API max (usually 5k-10k candles), the oldest data won't be fetched.")
    elif data_source_opt == "Yahoo Finance":
        st.caption("Note: Yahoo Finance limits intraday (1m, 5m, 1h) searches to the last 30-70 days, but has unlimited Daily/Weekly history.")
    elif data_source_opt == "Moneycontrol":
        st.caption("Note: Moneycontrol allows up to 1 year of intraday (1m, 5m, 1h) data and 25+ years of Daily history in a single call. Fetched data will be merged with your local CSV to preserve older history.")
    
    if st.button("Fetch Data", type="primary"):
        with st.spinner(f"Fetching {symbol} from {start_date_fetch} to {end_date_fetch} via {data_source_opt}..."):
            try:
                from tvDatafeed import Interval
                import importlib
                import fetch_data
                importlib.reload(fetch_data)
                from fetch_data import fetch_data_hub
                
                if data_source_opt == "TradingView":
                    interval_tv_enum = getattr(Interval, interval_selection)
                    interval_yf_str = None
                else:
                    interval_tv_enum = None
                    interval_yf_str = interval_selection
                
                filepath, err_msg = fetch_data_hub(data_source_opt, symbol, exchange, interval_tv_enum, interval_yf_str,
                                          start_date=str(start_date_fetch), end_date=str(end_date_fetch))
                
                if filepath:
                    st.success(f"Successfully fetched data and saved to: {filepath}")
                    st.session_state['data_fetched'] = True
                    st.session_state['last_fetched_file'] = filepath
                else:
                    st.error(err_msg)
            except Exception as e:
                st.error(f"An error occurred: {e}")
                
    # Data Quality Check UI
    if 'last_fetched_file' in st.session_state and os.path.exists(st.session_state['last_fetched_file']):
        st.divider()
        st.subheader("Data Quality Inspection")
        fp = st.session_state['last_fetched_file']
        
        try:
            df_dq = pd.read_csv(fp, index_col=0, parse_dates=True)
            
            # Count missing values across all columns
            total_nans = df_dq.isna().sum().sum()
            # Count zero volume rows (if volume exists)
            zero_vols = 0
            if 'Volume' in df_dq.columns:
                zero_vols = (df_dq['Volume'] == 0).sum()
                
            total_issues = total_nans + zero_vols
            
            if total_issues == 0:
                st.success(f"Data Quality Check Passed. 0 missing values or zero-volume anomalies found in `{os.path.basename(fp)}`. Ready to backtest.")
            else:
                st.warning(f"**Data Quality Issues Detected in `{os.path.basename(fp)}`.**\n\nFound {total_nans} missing (NaN) values and {zero_vols} zero-volume rows.")
                
                # Extract and display the bad rows
                st.write("**Preview of rows with anomalies:**")
                mask_na = df_dq.isna().any(axis=1)
                mask_vol = (df_dq.get('Volume', pd.Series(1, index=df_dq.index)) == 0)
                bad_rows = df_dq[mask_na | mask_vol]
                st.dataframe(bad_rows)
                
                fix_method = st.radio("Select a repair method:", [
                    "Drop Rows (Deletes incomplete candles)", 
                    "Forward Fill (Carries previous close price forward)",
                    "Linear Interpolation (Mathematically smooths the gap)"
                ])
                
                if st.button("Apply Fix", type="primary"):
                    with st.spinner("Applying repair..."):
                        if "Drop Rows" in fix_method:
                            df_clean = df_dq.dropna()
                            if 'Volume' in df_clean.columns:
                                df_clean = df_clean[df_clean['Volume'] > 0]
                        elif "Forward Fill" in fix_method:
                            df_clean = df_dq.ffill()
                        else:  # Interpolation
                            df_clean = df_dq.interpolate(method='linear')
                            
                        # Resave
                        df_clean.to_csv(fp)
                        st.success(f"Fixed applied! Overwrote `{os.path.basename(fp)}` with clean data.")
                        
                        # Clear state to reset UI
                        del st.session_state['last_fetched_file']
                        st.rerun()
                        
        except Exception as e:
            st.error(f"Could not perform Data Quality check: {e}")

def run_strategy_diagnostics(code_string):
    """Run interactive compilation, syntax structure, and dry-run tests on the strategy code."""
    results = {
        "syntax": {"status": "Pending", "msg": "Not started"},
        "structure": {"status": "Pending", "msg": "Not started"},
        "dry_run": {"status": "Pending", "msg": "Not started"},
        "success": False
    }
    
    # 1. Syntax Check
    try:
        ast.parse(code_string)
        results["syntax"] = {"status": "Passed", "msg": "Python code parsed successfully."}
    except SyntaxError as se:
        error_msg = f"SyntaxError at line {se.lineno}, col {se.offset}: {se.msg}\n\nLine: {se.text}"
        results["syntax"] = {"status": "Failed", "msg": error_msg}
        return results
    except Exception as e:
        results["syntax"] = {"status": "Failed", "msg": f"Parser error: {str(e)}"}
        return results

    # 2. Structural & Class Inheritance Check
    try:
        local_scope = {
            'Strategy': Strategy,
            'Backtest': Backtest,
            'pd': pd,
            'np': np
        }
        
        exec(code_string, local_scope)
        
        # Find Strategy class
        strat_class = None
        for name, obj in local_scope.items():
            if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy:
                strat_class = obj
                break
                
        if not strat_class:
            results["structure"] = {
                "status": "Failed",
                "msg": "No subclass of 'backtesting.Strategy' was found in the code. Ensure you define a class (e.g., MyStrategy) that inherits from Strategy."
            }
            return results
            
        # Check methods
        methods = dir(strat_class)
        has_init = 'init' in methods
        has_next = 'next' in methods
        
        if not has_init or not has_next:
            missing = []
            if not has_init: missing.append("init()")
            if not has_next: missing.append("next()")
            results["structure"] = {
                "status": "Failed",
                "msg": f"Strategy class '{strat_class.__name__}' is missing mandatory methods: {', '.join(missing)}."
            }
            return results
            
        results["structure"] = {
            "status": "Passed",
            "msg": f"Found valid strategy class '{strat_class.__name__}' with init() and next() methods.",
            "class": strat_class
        }
    except Exception as e:
        tb = traceback.format_exc()
        results["structure"] = {
            "status": "Failed",
            "msg": f"Failed to load or execute strategy definition:\n\n{tb}"
        }
        return results

    # 3. Dry-Run Execution Test
    try:
        strat_class = results["structure"]["class"]
        
        # Generate 200 rows of synthetic price data
        dummy_df = pd.DataFrame({
            'Open': np.linspace(100, 110, 200) + np.random.randn(200),
            'High': np.linspace(101, 111, 200) + np.random.randn(200),
            'Low': np.linspace(99, 109, 200) + np.random.randn(200),
            'Close': np.linspace(100, 110, 200) + np.random.randn(200),
            'Volume': [1000] * 200
        }, index=pd.date_range(start='2026-01-01', periods=200, freq='D'))
        
        bt = Backtest(
            dummy_df, 
            strat_class, 
            cash=10000,
            commission=0.0, 
            spread=0.0,
            margin=1.0,
            trade_on_close=False,
            hedging=False,
            exclusive_orders=True,
            finalize_trades=True
        )
        
        bt.run()
        results["dry_run"] = {
            "status": "Passed",
            "msg": "Strategy ran successfully on 200 rows of test data with zero exceptions."
        }
        results["success"] = True
    except Exception as e:
        tb = traceback.format_exc()
        results["dry_run"] = {
            "status": "Failed",
            "msg": f"Runtime error during execution simulation:\n\n{tb}"
        }
        
    return results

# --- TAB 2: Strategy Editor ---
if active_tab == "Strategy Editor":
    st.header("Strategy IDE")
    st.write("Create a new strategy or edit an existing one. Use the integrated IDE to test for syntax and runtime errors.")
    
    # Session state initialization for tracking edits and preventing resets
    if 'strategy_code_state' not in st.session_state:
        st.session_state['strategy_code_state'] = ""
    if 'prev_selected_file' not in st.session_state:
        st.session_state['prev_selected_file'] = None
    if 'prev_editor_mode' not in st.session_state:
        st.session_state['prev_editor_mode'] = None
        
    editor_mode = st.radio("Mode:", ["Create New Strategy", "Edit Existing Strategy"], horizontal=True)
    
    strategies_dir = "strategies"
    if not os.path.exists(strategies_dir):
        os.makedirs(strategies_dir)
        
    strategy_code = ""
    strategy_name_input = ""
    
    default_template = '''from backtesting import Strategy
from backtesting.lib import crossover
import pandas as pd

def SMA(val, period):
    return pd.Series(val).rolling(period).mean()

class MySmaCross(Strategy):
    n1 = 10
    n2 = 20

    def init(self):
        # Precompute indicators
        self.sma1 = self.I(SMA, self.data.Close, self.n1)
        self.sma2 = self.I(SMA, self.data.Close, self.n2)

    def next(self):
        # Entry/Exit Logic
        if crossover(self.sma1, self.sma2):
            self.position.close()
            self.buy()
        elif crossover(self.sma2, self.sma1):
            self.position.close()
            self.sell()
'''

    if editor_mode == "Create New Strategy":
        strategy_name_input = st.text_input("Save Strategy As (filename without extension):", value="my_strategy")
        if st.session_state['prev_editor_mode'] != "Create New Strategy":
            st.session_state['strategy_code_state'] = default_template
            st.session_state['prev_editor_mode'] = "Create New Strategy"
            st.session_state['prev_selected_file'] = None
    else:
        strategy_files = [f for f in os.listdir(strategies_dir) if f.endswith('.py')]
        if not strategy_files:
            st.warning("No existing strategies found in the `strategies/` directory.")
            st.session_state['strategy_code_state'] = ""
        else:
            selected_edit_file = st.selectbox("Select Strategy to Edit:", strategy_files)
            
            st.write("If you change the name below, it will save as a NEW copy instead of overwriting.")
            strategy_name_input = st.text_input("Save Strategy As (filename without extension):", value=selected_edit_file.replace('.py', ''))
            
            if st.session_state['prev_editor_mode'] != "Edit Existing Strategy" or st.session_state['prev_selected_file'] != selected_edit_file:
                edit_filepath = os.path.join(strategies_dir, selected_edit_file)
                try:
                    with open(edit_filepath, "r", encoding="utf-8") as f:
                        st.session_state['strategy_code_state'] = f.read()
                except Exception as e:
                    st.error(f"Failed to read file: {e}")
                    st.session_state['strategy_code_state'] = ""
                st.session_state['prev_editor_mode'] = "Edit Existing Strategy"
                st.session_state['prev_selected_file'] = selected_edit_file

    st.markdown("---")
    
    # 2 Columns for IDE: Left = Editor & Console, Right = Settings
    col_editor, col_settings = st.columns([8, 3])
    
    with col_settings:
        st.markdown("#### IDE Configuration")
        themes_list = ["monokai", "dracula", "tomorrow_night", "twilight", "github", "tomorrow", "xcode", "solarized_dark", "solarized_light"]
        bindings_list = ["vscode", "vim", "emacs", "sublime"]
        
        theme_idx = themes_list.index(st.session_state['ide_theme']) if st.session_state['ide_theme'] in themes_list else 1
        binding_idx = bindings_list.index(st.session_state['ide_keybinding']) if st.session_state['ide_keybinding'] in bindings_list else 0
        
        theme = st.selectbox(
            "Editor Theme",
            themes_list,
            index=theme_idx,
            help="Choose your preferred visual styling theme."
        )
        st.session_state['ide_theme'] = theme
        
        keybinding = st.selectbox(
            "Keybinding Model",
            bindings_list,
            index=binding_idx,
            help="Choose the editor keybindings (e.g. support for vim navigation or standard vscode bindings)."
        )
        st.session_state['ide_keybinding'] = keybinding
        
        font_size = st.slider("Font Size", 10, 24, st.session_state['ide_font_size'], step=1)
        st.session_state['ide_font_size'] = font_size
        
        tab_size_idx = [2, 4, 8].index(st.session_state['ide_tab_size']) if st.session_state['ide_tab_size'] in [2, 4, 8] else 1
        tab_size = st.selectbox("Tab Width", [2, 4, 8], index=tab_size_idx)
        st.session_state['ide_tab_size'] = tab_size
        
        wrap_lines = st.checkbox("Word Wrap", value=st.session_state['ide_wrap_lines'])
        st.session_state['ide_wrap_lines'] = wrap_lines
        
        show_gutter = st.checkbox("Show Line Numbers", value=st.session_state['ide_show_gutter'])
        st.session_state['ide_show_gutter'] = show_gutter
        
    with col_editor:
        st.markdown("#### Source Code")
        # Render the custom streamlit-ace editor
        final_code = st_ace(
            value=st.session_state['strategy_code_state'],
            language="python",
            theme=st.session_state['ide_theme'],
            keybinding=st.session_state['ide_keybinding'],
            font_size=st.session_state['ide_font_size'],
            tab_size=st.session_state['ide_tab_size'],
            wrap=st.session_state['ide_wrap_lines'],
            show_gutter=st.session_state['ide_show_gutter'],
            height=450,
            auto_update=False,  # Update code on blur/save to avoid redraw latency while typing
            key="strategy_ace_editor"
        )
        
        # Keep code state updated
        st.session_state['strategy_code_state'] = final_code
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            test_btn = st.button("Compile & Test", use_container_width=True)
        with btn_col2:
            save_btn = st.button("Save Strategy", type="primary", use_container_width=True)
            
        # Diagnostics Trigger
        if test_btn:
            with st.spinner("Running syntax & runtime sanity tests..."):
                diagnostics_results = run_strategy_diagnostics(final_code)
                st.session_state['editor_diagnostics'] = diagnostics_results
                
        # Save Trigger
        if save_btn:
            if not strategy_name_input:
                st.error("Please provide a filename.")
            else:
                filename = os.path.join(strategies_dir, f"{strategy_name_input}.py")
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(final_code)
                    st.success(f"Strategy successfully saved to `{filename}`")
                    # Clear prev state so it forces re-read of newly saved strategy (especially if renamed)
                    st.session_state['prev_selected_file'] = f"{strategy_name_input}.py"
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save strategy: {e}")

    # Diagnostics Console Rendering (Always visible below if ran)
    if 'editor_diagnostics' in st.session_state:
        st.divider()
        diag = st.session_state['editor_diagnostics']
        st.subheader("Diagnostics Console")
        
        # Status Badges
        c1, c2, c3 = st.columns(3)
        
        def render_indicator(name, step_data):
            status = step_data["status"]
            if status == "Passed":
                st.success(f"PASS  {name}")
            elif status == "Failed":
                st.error(f"FAIL  {name}")
            else:
                st.info(f"PENDING  {name}")
                
        with c1:
            render_indicator("Syntax Compiler Check", diag["syntax"])
        with c2:
            render_indicator("Strategy Subclass & Method Check", diag["structure"])
        with c3:
            render_indicator("Mock execution (200 Days Dry-Run)", diag["dry_run"])
            
        # Failure Traceback / Console Log
        if not diag["success"]:
            st.markdown("### Compilation & Runtime Diagnostics")
            for step in ["syntax", "structure", "dry_run"]:
                if diag[step]["status"] == "Failed":
                    st.error(f"Error in step: **{step.replace('_', ' ').title()}**")
                    st.code(diag[step]["msg"], language="text")
        else:
            st.success("All checks passed. Your strategy is syntactically correct and executed successfully on the mock backtest simulator. It is ready for historical backtesting.")

# --- TAB 3: Run Backtest ---
if active_tab == "Run Backtest":
    sub_tab_ind, sub_tab_blk = st.tabs(["Individual Run", "Bulk Run"])
    
    with sub_tab_ind:
        st.header("Run Backtest")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("1. Select Dataset")
            data_dir = "data"
            data_files = []
            if os.path.exists(data_dir):
                data_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]

            if not data_files:
                st.warning("No data found. Go to 'Fetch Data' tab first.")
                selected_data = None
            else:
                selected_data = st.selectbox("Dataset (CSV)", data_files)

                # Timeframe resampling option
                resample_tf = st.selectbox(
                    "Resample Timeframe (Before Backtesting)",
                    ["No Resampling (Use Native)", "5 Min ('5T')", "15 Min ('15T')", "30 Min ('30T')", "1 Hour ('1H')", "4 Hours ('4H')", "1 Day ('1D')"],
                    help="Resample the granular dataset to a higher timeframe before running the strategy."
                )

                # --- Date Slicer UI ---
                if selected_data:
                    try:
                        df_preview = pd.read_csv(os.path.join(data_dir, selected_data))
                        df_preview.columns = df_preview.columns.str.strip()
                        dt_col = None
                        for col in df_preview.columns:
                            if col.lower() in ['date', 'time', 'datetime', 'timestamp']:
                                dt_col = col
                                break
                        if dt_col:
                            df_preview[dt_col] = pd.to_datetime(df_preview[dt_col], format='mixed')
                            min_date = df_preview[dt_col].min().date()
                            max_date = df_preview[dt_col].max().date()

                            st.write(f"Available from **{min_date}** to **{max_date}**")

                            # Add Time Slicing support for intraday data
                            # We use two separate rows: Start (Date + Time) and End (Date + Time)
                            st.markdown("**Filter Data Range**")
                            d_col1, d_col2 = st.columns(2)

                            import datetime
                            with d_col1:
                                start_d = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
                                start_t = st.time_input("Start Time", value=datetime.time(0, 0))
                            with d_col2:
                                end_d = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
                                end_t = st.time_input("End Time", value=datetime.time(23, 59))

                            # Combine them into full datetime objects
                            start_datetime = datetime.datetime.combine(start_d, start_t)
                            end_datetime = datetime.datetime.combine(end_d, end_t)

                        else:
                            start_datetime, end_datetime = None, None
                    except Exception as e:
                        start_datetime, end_datetime = None, None
                        st.warning(f"Could not load dates for preview: {e}")
                else:
                    start_datetime, end_datetime = None, None

        with col2:
            st.subheader("2. Select Strategy")
            strategies_dir = "strategies"
            strategy_files = []
            if os.path.exists(strategies_dir):
                strategy_files = [f for f in os.listdir(strategies_dir) if f.endswith('.py')]

            if not strategy_files:
                st.warning("No strategies found. Go to 'Strategy Editor' to save one.")
                selected_strategy_file = None
            else:
                selected_strategy_file = st.selectbox("Strategy File", strategy_files)

        # 3. Advanced Parameters
        st.subheader("3. Backtest Parameters")
        with st.expander("Configure Parameters", expanded=True):
            p1, p2, p3 = st.columns(3)
            with p1:
                init_cash = st.number_input("Initial Cash", min_value=1, value=10000, step=1000, 
                                            help="The initial capital to start the backtest with. Example: 10000 means starting with $10,000.")
                margin = st.number_input("Margin (1.0 = No Leverage)", min_value=0.01, max_value=1.0, value=1.0, step=0.01,
                                         help="Required margin (ratio) of a leveraged account. Set to 1.0 for a cash account (no leverage). Set to e.g., 0.02 (1/50) for 50:1 leverage.")
            with p2:
                commission = st.number_input("Commission (e.g., 0.002 = 0.2%)", min_value=0.0, max_value=0.1, value=0.0, step=0.001, format="%.4f",
                                             help="The commission rate as a fraction. Example: If your broker charges 0.2% per trade, set to 0.002. Applied on both entry and exit.")
                spread = st.number_input("Spread / Slippage", min_value=0.0, max_value=0.1, value=0.0, step=0.0001, format="%.4f",
                                         help="Constant bid-ask spread rate relative to the price. Useful for simulating slippage. Example: 0.0002 for 0.02% slippage.")
            with p3:
                trade_on_close = st.checkbox("Trade on Close", value=False,
                                             help="If enabled, market orders will be filled at the current bar's closing price instead of the next bar's open.")
                hedging = st.checkbox("Allow Hedging", value=False,
                                      help="If enabled, allows you to be in Long and Short positions simultaneously. If disabled, opposite-facing orders will close existing trades first.")
                exclusive_orders = st.checkbox("Exclusive Orders", value=True,
                                               help="If enabled, every new order automatically closes the previous position, ensuring at most a single trade is active at a time.")
                finalize_trades = st.checkbox("Finalize Trades", value=True,
                                              help="If enabled, any open positions at the end of the backtest dataset will be automatically 'closed' at the last available price to realize their final PnL in the statistics.")

        st.markdown("---")

        # 4. Final Execution Code Override
        st.subheader("4. Execution Script")
        st.write("You can review and manually override the execution script before running. Note: `df`, `strat_class`, and parameter variables (like `init_cash`, `commission`) are available in the scope.")

        import textwrap
        default_exec_code = textwrap.dedent("""\
            # Initialize Backtest
            bt = Backtest(
                df, 
                strat_class, 
                cash=init_cash,
                commission=commission, 
                spread=spread,
                margin=margin,
                trade_on_close=trade_on_close,
                hedging=hedging,
                exclusive_orders=exclusive_orders,
                finalize_trades=finalize_trades
            )

            # Run standard backtest
            stats = bt.run()

            # Alternatively, you can use bt.optimize() here instead if you want to optimize parameters.
            """)
        if 'exec_code_state' not in st.session_state:
            st.session_state['exec_code_state'] = default_exec_code.strip()

        exec_code = st_ace(
            value=st.session_state['exec_code_state'],
            language="python",
            theme=st.session_state.get('ide_theme', 'dracula'),
            keybinding=st.session_state.get('ide_keybinding', 'vscode'),
            font_size=st.session_state.get('ide_font_size', 14),
            tab_size=st.session_state.get('ide_tab_size', 4),
            wrap=st.session_state.get('ide_wrap_lines', True),
            show_gutter=st.session_state.get('ide_show_gutter', True),
            height=280,
            auto_update=False,
            key="backtest_execution_editor"
        )
        st.session_state['exec_code_state'] = exec_code

        col_reset, col_spacer = st.columns([4, 6])
        with col_reset:
            if st.button("Reset Script to Default"):
                st.session_state['exec_code_state'] = default_exec_code.strip()
                st.rerun()

        if st.button("Run Script", type="primary", use_container_width=True):
            if selected_data and selected_strategy_file:
                with st.spinner("Executing user script..."):
                    try:
                        # 1. Load Data
                        df = pd.read_csv(os.path.join(data_dir, selected_data))

                        # Ensure column names are stripped of whitespace
                        df.columns = df.columns.str.strip()

                        # Rename standard columns to Title Case expected by Backtesting.py
                        col_map = {c.lower(): c.capitalize() for c in df.columns}
                        df.rename(columns=col_map, inplace=True)
                        if 'Volume' not in df.columns and 'volume' in col_map: 
                            df.rename(columns={'volume': 'Volume'}, inplace=True) # Edge case for volume

                        # Locate Date/Time column
                        datetime_col = None
                        for col in df.columns:
                            if col.lower() in ['date', 'time', 'datetime', 'timestamp', 'unnamed: 0']:
                                datetime_col = col
                                break

                        if datetime_col:
                            # Auto-parse arbitrary datetime formats (e.g. 8/19/2004)
                            df[datetime_col] = pd.to_datetime(df[datetime_col], format='mixed')
                            df.set_index(datetime_col, inplace=True)
                            if df.index.tz is not None:
                                df.index = df.index.tz_localize(None)
                            df.sort_index(inplace=True)

                            # Apply DateTime Slicing
                            if start_datetime and end_datetime:
                                # Convert to format matching pandas index
                                try:
                                    start_dt_pd = pd.to_datetime(start_datetime)
                                    end_dt_pd = pd.to_datetime(end_datetime)
                                    mask = (df.index >= start_dt_pd) & (df.index <= end_dt_pd)
                                    df = df.loc[mask]
                                    if df.empty:
                                        st.error("DateTime slice resulted in an empty dataset. Please broaden the range.")
                                        st.stop()
                                except Exception as e:
                                    st.warning(f"Error applying datetime slice: {e}. Running on full dataset.")

                            # Apply Timeframe Resampling
                            if resample_tf != "No Resampling (Use Native)":
                                tf_map = {
                                    "5 Min ('5T')": "5T",
                                    "15 Min ('15T')": "15T",
                                    "30 Min ('30T')": "30T",
                                    "1 Hour ('1H')": "1H",
                                    "4 Hours ('4H')": "4H",
                                    "1 Day ('1D')": "1D"
                                }
                                rule = tf_map.get(resample_tf)
                                if rule:
                                    try:
                                        resample_dict = {}
                                        if 'Open' in df.columns: resample_dict['Open'] = 'first'
                                        if 'High' in df.columns: resample_dict['High'] = 'max'
                                        if 'Low' in df.columns: resample_dict['Low'] = 'min'
                                        if 'Close' in df.columns: resample_dict['Close'] = 'last'
                                        if 'Volume' in df.columns: resample_dict['Volume'] = 'sum'
                                        for col in df.columns:
                                            if col not in resample_dict:
                                                resample_dict[col] = 'first'
                                        df = df.resample(rule).agg(resample_dict).dropna()
                                        st.info(f"Resampled dataset to `{rule}` timeframe. New shape: {df.shape}")
                                    except Exception as resample_err:
                                        st.warning(f"Failed to resample: {resample_err}. Running on native data.")

                        elif not pd.api.types.is_datetime64_any_dtype(df.index):
                            st.warning("Could not identify a clear Datetime column. The backtester index might be missing timestamps.")

                        # 2. Load Strategy
                        strat_class = load_strategy(os.path.join(strategies_dir, selected_strategy_file))
                        if not strat_class:
                            st.error("No valid Strategy class found in the file.")
                            st.stop()

                        # 3. Dynamic Execution
                        # Define the local context for the script
                        local_context = {
                            'Backtest': Backtest,
                            'df': df,
                            'strat_class': strat_class,
                            'init_cash': init_cash,
                            'commission': commission,
                            'spread': spread,
                            'margin': margin,
                            'trade_on_close': trade_on_close,
                            'hedging': hedging,
                            'exclusive_orders': exclusive_orders,
                            'finalize_trades': finalize_trades
                        }

                        # Execute the user's override script
                        import textwrap
                        exec(textwrap.dedent(exec_code), {}, local_context)

                        # Retrieve the results from the executed context
                        if 'stats' not in local_context:
                            st.error("The script must assign the results to a variable named `stats` (e.g., stats = bt.run()).")
                            st.stop()

                        stats = local_context['stats']
                        if 'bt' in local_context:
                            bt = local_context['bt']
                        else:
                            st.warning("`bt` object was not found, interactive plotting will be disabled.")
                            bt = None

                        # 4. Save results to disk automatically
                        import datetime
                        if not os.path.exists("results"):
                            os.makedirs("results")

                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        report_name = f"{selected_strategy_file.replace('.py', '')}_{selected_data.replace('.csv', '')}_{timestamp}"

                        # Save stats
                        stats_file = os.path.join("results", f"{report_name}_stats.csv")
                        stats.drop(['_strategy', '_equity_curve', '_trades']).to_csv(stats_file)

                        # Save trades
                        trades_df = stats['_trades'] if '_trades' in stats else pd.DataFrame()
                        trades_file = os.path.join("results", f"{report_name}_trades.csv")
                        if not trades_df.empty:
                            trades_df.to_csv(trades_file, index=False)

                        # Generate and save Bokeh interactive chart
                        plot_file = os.path.abspath(os.path.join("results", f"{report_name}_plot.html"))
                        if bt is not None:
                            if len(df) <= 10000:
                                try:
                                    bt.plot(filename=plot_file, open_browser=False)
                                except Exception as plot_err:
                                    st.warning(f"Failed to generate interactive Bokeh chart: {plot_err}")
                                    plot_file = None
                            else:
                                plot_file = None
                                st.info("Interactive chart disabled for datasets > 10,000 bars to prevent browser lagging. Use a smaller date range or Resample to enable it.")
                        else:
                            plot_file = None

                        # 5. Extract Metrics & Run Monte Carlo
                        metrics = calculate_strategy_metrics(stats, trades_df)

                        mc_results = None
                        if not trades_df.empty and 'ReturnPct' in trades_df.columns:
                            returns = trades_df['ReturnPct'].values / 100.0
                            if len(returns) >= 5:
                                mc_results = run_monte_carlo_sim(returns, n_simulations=1000, confidence_level=95, start_capital=init_cash)

                        # 6. Render Unified Dashboard
                        st.success(f"Backtest successfully executed! (Saved as: `{report_name}`)")

                        render_unified_dashboard(report_name, metrics, trades_df, plot_file, mc_results)

                        # 7. Alpha Comparison
                        st.subheader("Benchmark Alpha Comparison")
                        
                        try:
                            from fetch_data import update_benchmark_data
                            # Pass the strategy equity curve's max date
                            latest_date = None
                            if '_equity_curve' in stats and not stats['_equity_curve'].empty:
                                latest_date = stats['_equity_curve'].index.max()
                            update_benchmark_data(latest_test_date=latest_date)
                        except Exception as update_err:
                            st.warning(f"Failed to auto-update benchmark data: {update_err}")

                        benchmark_path = "data/benchmark_nifty50.csv"

                        if os.path.exists(benchmark_path) and '_equity_curve' in stats:
                            try:
                                # Load Benchmark
                                bm_df = pd.read_csv(benchmark_path, index_col=0, parse_dates=True)
                                bm_df.index = pd.to_datetime(bm_df.index, utc=True).tz_localize(None)
                                bm_df.sort_index(inplace=True)
                                bm_df = bm_df[~bm_df.index.duplicated(keep='last')]

                                # Extract Strategy Equity
                                strat_equity = stats['_equity_curve']['Equity']
                                strat_equity.index = pd.to_datetime(strat_equity.index, utc=True).tz_localize(None)
                                strat_equity = strat_equity[~strat_equity.index.duplicated(keep='last')].sort_index()

                                # Reindex Benchmark to perfectly match strategy date points (forward filling missing granularity)
                                bm_aligned = bm_df['Close'].reindex(strat_equity.index, method='ffill')

                                valid_start = bm_aligned.first_valid_index()
                                if valid_start:
                                    strat_eq_clean = strat_equity.loc[valid_start:]
                                    bm_clean = bm_aligned.loc[valid_start:]

                                    # Normalize both to start at 0%
                                    strat_ret_pct = (strat_eq_clean / strat_eq_clean.iloc[0] - 1) * 100
                                    bm_ret_pct = (bm_clean / bm_clean.iloc[0] - 1) * 100

                                    # Compile for rendering
                                    alpha_df = pd.DataFrame({
                                        'Strategy Return (%)': strat_ret_pct,
                                        'Nifty 50 Benchmark (%)': bm_ret_pct
                                    })

                                    final_alpha = strat_ret_pct.iloc[-1] - bm_ret_pct.iloc[-1]
                                    a_col1, a_col2 = st.columns([8, 2])
                                    with a_col1:
                                        if len(alpha_df) > 1000:
                                            import numpy as np
                                            indices = np.linspace(0, len(alpha_df) - 1, 1000, dtype=int)
                                            alpha_df_plot = alpha_df.iloc[indices]
                                        else:
                                            alpha_df_plot = alpha_df
                                        st.line_chart(alpha_df_plot, use_container_width=True)
                                    with a_col2:
                                        st.metric("Strategy Total", f"{strat_ret_pct.iloc[-1]:.2f}%")
                                        st.metric("Benchmark Total", f"{bm_ret_pct.iloc[-1]:.2f}%")
                                        st.metric("Net Alpha", f"{final_alpha:.2f}%", delta=f"{final_alpha:.2f}%")
                                else:
                                    st.warning("Strategy dates are completely outside the Nifty 50 benchmark range.")
                            except Exception as alpha_err:
                                st.warning(f"Failed to generate Alpha chart: {alpha_err}")
                        else:
                            st.info("Nifty 50 benchmark data missing. Skipping alpha compilation.")

                    except Exception as e:
                        st.error(f"Error during backtest: {e}")
            else:
                st.error("Please select both a dataset and a strategy.")

    
    with sub_tab_blk:
        st.header("Bulk Testing Engine")
        st.write("Automatically slice your dataset into individual periods (e.g., Daily) and run your strategy on each slice independently to rank performance.")

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            data_dir = "data"
            data_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')] if os.path.exists(data_dir) else []

            st.info("**Note:** When selecting multiple datasets, ensure they all share the same Native Granularity (e.g., all 5-minute tickers, or all Daily).")
            selected_bulk_data = st.multiselect("Select Datasets", data_files, key="bulk_data", help="Select one or more historical datasets to test against.")

            # --- Date Slicer UI (from Tab 3) ---
            if selected_bulk_data:
                try:
                    min_dates, max_dates = [], []
                    for ds in selected_bulk_data:
                        df_preview = pd.read_csv(os.path.join(data_dir, ds))
                        df_preview.columns = df_preview.columns.str.strip()
                        dt_col = next((c for c in df_preview.columns if c.lower() in ['date', 'time', 'datetime', 'timestamp']), None)
                        if dt_col:
                            df_preview[dt_col] = pd.to_datetime(df_preview[dt_col], format='mixed')
                            min_dates.append(df_preview[dt_col].min().date())
                            max_dates.append(df_preview[dt_col].max().date())

                    if min_dates and max_dates:
                        global_min = max(min_dates)
                        global_max = min(max_dates)

                        if global_min <= global_max:
                            st.success(f"Combined Data Overlap Available: **{global_min}** to **{global_max}**")
                        else:
                            st.warning("**No overlapping dates found between the selected datasets.**")
                            global_min, global_max = min(min_dates), max(max_dates)

                        st.markdown("**Filter Data Range**")
                        d_col1, d_col2 = st.columns(2)

                        import datetime
                        with d_col1:
                            start_d = st.date_input("Start Date", value=global_min, key="b_sd")
                            start_t = st.time_input("Start Time", value=datetime.time(0, 0), key="b_st")
                        with d_col2:
                            end_d = st.date_input("End Date", value=global_max, key="b_ed")
                            end_t = st.time_input("End Time", value=datetime.time(23, 59), key="b_et")

                        start_datetime_bulk = datetime.datetime.combine(start_d, start_t)
                        end_datetime_bulk = datetime.datetime.combine(end_d, end_t)

                    else:
                        start_datetime_bulk, end_datetime_bulk = None, None
                except Exception as e:
                    start_datetime_bulk, end_datetime_bulk = None, None
                    st.warning(f"Could not load dates for preview: {e}")
            else:
                start_datetime_bulk, end_datetime_bulk = None, None

        with b_col2:
            strategies_dir = "strategies"
            strategy_files = [f for f in os.listdir(strategies_dir) if f.endswith('.py')] if os.path.exists(strategies_dir) else []
            selected_bulk_strat = st.selectbox("Select Strategy", strategy_files, key="bulk_strat")

        split_freq = st.selectbox("Split Dataset By:", ["Whole Dataset (No Split)", "Daily", "Weekly", "Monthly", "Intraday (Time Windows)", "Resample Timeframes"], help="Choose 'Whole Dataset' to test across the entire filtered date range without breaking it down. Select 'Intraday' to test specific hours within each day. Select 'Resample Timeframes' to test across multiple candle intervals.")

        # Intraday dynamic UI
        intraday_windows = []
        if split_freq == "Intraday (Time Windows)":
            st.markdown("**Define Intraday Windows**")
            num_windows = st.number_input("Number of Time Windows per Day", min_value=1, max_value=5, value=2, step=1)
            import datetime
            for w in range(num_windows):
                c1, c2 = st.columns(2)
                with c1:
                    w_start = st.time_input(f"Window {w+1} Start", value=datetime.time(9 + w, 0), key=f"w_s_{w}")
                with c2:
                    w_end = st.time_input(f"Window {w+1} End", value=datetime.time(10 + w, 0), key=f"w_e_{w}")
                intraday_windows.append((w_start, w_end))

        # Resample Timeframes dynamic UI
        bulk_resample_tfs = []
        if split_freq == "Resample Timeframes":
            st.markdown("**Select Timeframes to Test**")
            tf_options = {
                "5 Min ('5T')": "5T",
                "15 Min ('15T')": "15T",
                "30 Min ('30T')": "30T",
                "1 Hour ('1H')": "1H",
                "4 Hours ('4H')": "4H",
                "1 Day ('1D')": "1D"
            }
            selected_tf_labels = st.multiselect(
                "Timeframes to Evaluate",
                options=list(tf_options.keys()),
                default=["5 Min ('5T')", "15 Min ('15T')", "1 Hour ('1H')", "1 Day ('1D')"],
                help="Select one or more timeframes to resample the granular dataset into."
            )
            bulk_resample_tfs = [tf_options[lbl] for lbl in selected_tf_labels]

        st.markdown("**(Uses the Advanced Parameters currently set in Tab 3 `Run Backtest`)**")

        # Estimate test count
        total_tests = 0
        test_details = []
        if selected_bulk_data:
            for ds in selected_bulk_data:
                try:
                    # Read only index/datetime column for speed
                    df_temp = pd.read_csv(os.path.join(data_dir, ds), nrows=5)
                    df_temp.columns = df_temp.columns.str.strip()
                    dt_col = next((c for c in df_temp.columns if c.lower() in ['date', 'time', 'datetime', 'timestamp']), None)
                    if dt_col:
                        df_ds = pd.read_csv(os.path.join(data_dir, ds), usecols=[dt_col])
                        df_ds.columns = df_ds.columns.str.strip()
                        df_ds[dt_col] = pd.to_datetime(df_ds[dt_col], format='mixed')
                        df_ds.set_index(dt_col, inplace=True)

                        if start_datetime_bulk and end_datetime_bulk:
                            start_dt_pd = pd.to_datetime(start_datetime_bulk)
                            end_dt_pd = pd.to_datetime(end_datetime_bulk)
                            df_ds = df_ds.loc[(df_ds.index >= start_dt_pd) & (df_ds.index <= end_dt_pd)]

                        if split_freq == "Whole Dataset (No Split)":
                            count = 1
                        elif split_freq == "Daily":
                            count = len(df_ds.index.normalize().unique())
                        elif split_freq == "Weekly":
                            count = len(df_ds.groupby([df_ds.index.isocalendar().year, df_ds.index.isocalendar().week]))
                        elif split_freq == "Monthly":
                            count = len(df_ds.groupby([df_ds.index.year, df_ds.index.month]))
                        elif split_freq == "Intraday (Time Windows)":
                            num_days = len(df_ds.index.normalize().unique())
                            count = num_days * len(intraday_windows)
                        elif split_freq == "Resample Timeframes":
                            count = len(bulk_resample_tfs)
                        else:
                            count = 0

                        total_tests += count
                        test_details.append(f"- `{ds}`: **{count}** tests")
                    else:
                        test_details.append(f"- `{ds}`: Datetime column not found")
                except Exception as e:
                    test_details.append(f"- `{ds}`: Error estimating ({e})")

            # Display the scale estimation
            st.markdown("### Bulk Backtest Scale Estimate")
            col_scale1, col_scale2 = st.columns([4, 6])
            with col_scale1:
                st.metric("Total Projected Runs", f"{total_tests}")
            with col_scale2:
                st.markdown("**Runs Breakdown:**")
                for detail in test_details:
                    st.markdown(detail)

            if total_tests > 100:
                st.warning("**Warning:** Running over 100 backtests might take some time depending on hardware and dataset size.")
            st.markdown("---")

        if st.button("Run Bulk Test", type="primary", use_container_width=True):
            if not selected_bulk_data or not selected_bulk_strat:
                st.error("Please select at least one dataset and a strategy.")
            elif split_freq == "Resample Timeframes" and not bulk_resample_tfs:
                st.error("Please select at least one timeframe to test.")
            else:
                with st.spinner(f"Running Bulk {split_freq} tests across {len(selected_bulk_data)} datasets..."):
                    try:
                        st.session_state['bulk_running'] = True
                        if os.path.exists("stop_flag.txt"):
                            try: os.remove("stop_flag.txt")
                            except: pass
                        
                        all_stats = []
                        all_trades_lists = []
                        
                        # Initialize global progress indicators
                        progress_bar_overall = st.progress(0.0)
                        status_text = st.empty()
                        completed_tests = 0
                        
                        import datetime
                        log_container = st.empty()
                        log_messages = []
                        
                        def add_log(msg, type="info"):
                            color_map = {
                                "info": "#00ff66",   # Green
                                "warning": "#ffcc00", # Yellow
                                "error": "#ff3333"    # Red
                            }
                            color = color_map.get(type, "#00ff66")
                            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                            log_messages.append(f"<span style='color: #888;'>[{timestamp}]</span> <span style='color: {color};'>[{type.upper()}]</span> {msg}")
                            if len(log_messages) > 150:
                                log_messages.pop(0)
                            # Display latest log at top
                            log_html = f"<div style='height: 150px; overflow-y: auto; border: 1px solid #262730; padding: 10px; font-family: monospace; font-size: 0.85rem; background-color: #0e1117; color: #fff; border-radius: 5px; line-height: 1.5;'>{'<br>'.join(reversed(log_messages))}</div>"
                            log_container.markdown(log_html, unsafe_allow_html=True)

                        # 1. Load Strategy
                        strat_class = load_strategy(os.path.join(strategies_dir, selected_bulk_strat))
                        if not strat_class:
                            st.error("No valid Strategy class found in the file.")
                            st.session_state['bulk_running'] = False
                            st.stop()

                        # 2. Iterate over all selected datasets
                        for ds_idx, dataset_file in enumerate(selected_bulk_data):
                            if os.path.exists("stop_flag.txt"):
                                st.warning("Bulk testing aborted by user.")
                                try: os.remove("stop_flag.txt")
                                except: pass
                                break
                            add_log(f"Processing Dataset {ds_idx+1}/{len(selected_bulk_data)}: {dataset_file}", "info")

                            df = pd.read_csv(os.path.join(data_dir, dataset_file))
                            df.columns = df.columns.str.strip()
                            col_map = {c.lower(): c.capitalize() for c in df.columns}
                            df.rename(columns=col_map, inplace=True)
                            if 'Volume' not in df.columns and 'volume' in col_map: 
                                df.rename(columns={'volume': 'Volume'}, inplace=True)

                            dt_col = None
                            for col in df.columns:
                                if col.lower() in ['date', 'time', 'datetime', 'timestamp', 'unnamed: 0']:
                                    dt_col = col
                                    break

                            if not dt_col:
                                add_log(f"Skipping {dataset_file}: No datetime column found.", "warning")
                                continue

                            df[dt_col] = pd.to_datetime(df[dt_col], format='mixed')
                            df.set_index(dt_col, inplace=True)
                            if df.index.tz is not None:
                                df.index = df.index.tz_localize(None)
                            df.sort_index(inplace=True)

                            # --- Granularity Validation ---
                            # Calculate the median time difference between rows to guess the dataset's native timeframe
                            if len(df) > 1:
                                median_diff = df.index.to_series().diff().median()

                                if split_freq == "Intraday (Time Windows)" and median_diff >= pd.Timedelta(days=1):
                                    add_log(f"Granularity Mismatch for {dataset_file}: You requested an Intraday split, but this dataset appears to only contain Daily candles. Skipping.", "error")
                                    continue

                                if split_freq == "Daily" and median_diff >= pd.Timedelta(days=7):
                                    add_log(f"Granularity Mismatch for {dataset_file}: You requested a Daily split, but this dataset appears to only contain Weekly/Monthly candles. Skipping.", "error")
                                    continue

                            # Apply DateTime Slicing
                            if start_datetime_bulk and end_datetime_bulk:
                                try:
                                    start_dt_pd = pd.to_datetime(start_datetime_bulk)
                                    end_dt_pd = pd.to_datetime(end_datetime_bulk)
                                    mask = (df.index >= start_dt_pd) & (df.index <= end_dt_pd)
                                    df = df.loc[mask]
                                    if df.empty:
                                        add_log(f"DateTime slice resulted in an empty dataset for {dataset_file}.", "warning")
                                        continue
                                except Exception as e:
                                    add_log(f"Error applying datetime slice: {e}. Running on full dataset.", "warning")


                            # 3. Create Chunks
                            chunks = []
                            sym_name = dataset_file.replace('.csv', '')

                            if split_freq == "Whole Dataset (No Split)":
                                chunks = [(f"{sym_name} | Full Range", df)]
                            elif split_freq == "Daily":
                                chunks = [(f"{sym_name} | " + str(group.index[0].date()), group) for _, group in df.groupby(df.index.date)]
                            elif split_freq == "Weekly":
                                chunks = [(f"{sym_name} | {group.index[0].isocalendar().year}-W{group.index[0].isocalendar().week:02d}", group) for _, group in df.groupby([df.index.isocalendar().year, df.index.isocalendar().week])]
                            elif split_freq == "Monthly":
                                chunks = [(f"{sym_name} | {group.index[0].year}-{group.index[0].month:02d}", group) for _, group in df.groupby([df.index.year, df.index.month])]
                            elif split_freq == "Intraday (Time Windows)":
                                for date, daily_df in df.groupby(df.index.date):
                                    for start_t, end_t in intraday_windows:
                                        try:
                                            s_str = start_t.strftime("%H:%M:%S")
                                            e_str = end_t.strftime("%H:%M:%S")
                                            window_df = daily_df.between_time(s_str, e_str)
                                            if not window_df.empty:
                                                label = f"{sym_name} | {date} ({s_str[:5]}-{e_str[:5]})"
                                                chunks.append((label, window_df))
                                        except Exception as e:
                                            add_log(f"Failed to slice window {s_str}-{e_str} on {date}: {e}", "warning")
                            elif split_freq == "Resample Timeframes":
                                for tf in bulk_resample_tfs:
                                    try:
                                        resample_dict = {}
                                        if 'Open' in df.columns: resample_dict['Open'] = 'first'
                                        if 'High' in df.columns: resample_dict['High'] = 'max'
                                        if 'Low' in df.columns: resample_dict['Low'] = 'min'
                                        if 'Close' in df.columns: resample_dict['Close'] = 'last'
                                        if 'Volume' in df.columns: resample_dict['Volume'] = 'sum'
                                        for col in df.columns:
                                            if col not in resample_dict:
                                                resample_dict[col] = 'first'

                                        resampled_df = df.resample(tf).agg(resample_dict).dropna()
                                        if not resampled_df.empty:
                                            chunks.append((f"{sym_name} | TF: {tf}", resampled_df))
                                    except Exception as e:
                                        add_log(f"Failed to resample {dataset_file} to {tf}: {e}", "warning")

                            if not chunks:
                                add_log(f"No valid data chunks found to process in {dataset_file}.", "warning")
                                continue

                            add_log(f"Generated {len(chunks)} {split_freq} slices for {dataset_file}. Executing engine...", "info")

                            # 4. Execute Loop for this dataset
                            for i, (chunk_label, chunk_df) in enumerate(chunks):
                                if os.path.exists("stop_flag.txt"):
                                    break
                                
                                if len(chunk_df) < 5:  # Skip tiny chunks (e.g. half days with no data)
                                    completed_tests += 1
                                    progress_bar_overall.progress(min(completed_tests / total_tests, 1.0))
                                    continue

                                bt = Backtest(
                                    chunk_df, 
                                    strat_class, 
                                    cash=init_cash,
                                    commission=commission, 
                                    spread=spread,
                                    margin=margin,
                                    trade_on_close=trade_on_close,
                                    hedging=hedging,
                                    exclusive_orders=exclusive_orders,
                                    finalize_trades=finalize_trades
                                )

                                stats = bt.run()

                                chunk_trades = stats['_trades'] if '_trades' in stats else pd.DataFrame()
                                if not chunk_trades.empty:
                                    t_copy = chunk_trades.copy()
                                    t_copy['Chunk'] = chunk_label
                                    all_trades_lists.append(t_copy)

                                # Calculate full institutional metrics for this chunk
                                chunk_metrics = calculate_strategy_metrics(stats, chunk_trades)
                                chunk_metrics_series = pd.Series(chunk_metrics)
                                chunk_metrics_series.name = chunk_label
                                all_stats.append(chunk_metrics_series)

                                # Update progress
                                completed_tests += 1
                                progress_bar_overall.progress(min(completed_tests / total_tests, 1.0))
                                status_text.write(f"**Progress**: Completed {completed_tests}/{total_tests} runs. Processing `{chunk_label}`...")
                                import time
                                time.sleep(0.005) # Yield CPU control to keep browser/Tornado responsive

                        # 5. Aggregate and Display
                        if all_stats:
                            results_df = pd.DataFrame(all_stats)

                            combined_trades_df = pd.DataFrame()
                            if all_trades_lists:
                                combined_trades_df = pd.concat(all_trades_lists, ignore_index=True)

                            st.success("Bulk Testing Complete!")

                            # --- Auto Export Results (to results/ folder) ---
                            results_dir = "results"
                            if not os.path.exists(results_dir):
                                os.makedirs(results_dir)

                            import datetime
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

                            if len(selected_bulk_data) > 1:
                                target_tag = "Multiple_Datasets"
                            else:
                                target_tag = selected_bulk_data[0].replace('.csv', '')

                            bulk_report_base = f"BULK_{split_freq}_{selected_bulk_strat.replace('.py', '')}_{target_tag}_{timestamp}"
                            bulk_stats_path = os.path.join(results_dir, f"{bulk_report_base}_stats.csv")
                            bulk_trades_path = os.path.join(results_dir, f"{bulk_report_base}_trades.csv")

                            results_df.to_csv(bulk_stats_path)
                            if not combined_trades_df.empty:
                                combined_trades_df.to_csv(bulk_trades_path, index=False)

                            st.info(f"Bulk files successfully exported to `results/`.")

                            # Show Combined Portfolio Performance
                            if not combined_trades_df.empty:
                                # 1. Extract stock name from the 'Chunk' column
                                combined_trades_df['Stock'] = combined_trades_df['Chunk'].apply(lambda x: str(x).split(' | ')[0])
                                
                                # 2. Consolidate metrics per Stock
                                stock_groups = combined_trades_df.groupby('Stock')
                                stock_summaries = []
                                for name, group_df in stock_groups:
                                    summary = calculate_stock_consolidation(name, group_df, init_cash)
                                    stock_summaries.append(summary)
                                    
                                stock_summary_df = pd.DataFrame(stock_summaries)
                                
                                # 3. Calculate true portfolio return
                                n_stocks = len(stock_summary_df) if not stock_summary_df.empty else 1
                                portfolio_start_capital = n_stocks * init_cash
                                portfolio_pnl = stock_summary_df['Total PnL ($)'].sum() if not stock_summary_df.empty else 0.0
                                portfolio_return_pct = (portfolio_pnl / portfolio_start_capital * 100) if portfolio_start_capital > 0 else 0.0
                                
                                st.markdown("---")
                                st.subheader("Combined Portfolio Performance")
                                st.write("Aggregated metrics treating all tested assets as an equal-weighted multi-asset portfolio.")
                                
                                port_metrics = calculate_strategy_metrics({}, combined_trades_df)
                                
                                p_mc_results = None
                                if 'ReturnPct' in combined_trades_df.columns:
                                    returns = combined_trades_df['ReturnPct'].values / 100.0
                                    if len(returns) >= 5:
                                        p_mc_results = run_monte_carlo_sim(returns, n_simulations=1000, confidence_level=95, start_capital=init_cash)

                                pm1, pm2, pm3, pm4, pm5 = st.columns(5)
                                pm1.metric("Portfolio Return", f"{portfolio_return_pct:.2f}%")
                                pm2.metric("Portfolio PnL", f"${portfolio_pnl:,.2f}")
                                pm3.metric("Combined Profit Factor", f"{port_metrics['Profit Factor']:.2f}")
                                pm4.metric("Combined Win Rate", f"{port_metrics['Win Rate [%]']:.2f}%")
                                pm5.metric("Total Portfolio Trades", f"{port_metrics['Total Trades']}")

                                # Render Portfolio Monte Carlo if available
                                if p_mc_results:
                                    with st.expander("Portfolio Monte Carlo Analysis", expanded=False):
                                        st.write(f"Expected Portfolio Final Equity: **${p_mc_results['expected_final_equity']:,.2f}**")
                                        st.write(f"Portfolio Median Drawdown: **{p_mc_results['median_max_drawdown']:.2f}%**")
                                        st.write(f"Portfolio 95% Value-at-Risk (VaR) Drawdown: **{p_mc_results['var_max_drawdown']:.2f}%**")

                                        # Plot portfolio histogram
                                        counts, bin_edges = np.histogram(p_mc_results['max_dds'], bins=20)
                                        bin_labels = [f"{x:.1f}%" for x in bin_edges[:-1]]
                                        port_hist_df = pd.DataFrame({
                                            'Count': counts
                                        }, index=bin_labels)
                                        st.bar_chart(port_hist_df, use_container_width=True)

                                # 4. Display Stock Consolidation
                                st.markdown("---")
                                st.subheader("Individual Asset Performance Consolidation")
                                st.write("Consolidated performance metrics for each unique stock/dataset across all tested sub-intervals.")
                                
                                if not stock_summary_df.empty:
                                    stock_summary_df = stock_summary_df.sort_values(by="Cumulative Return [%]", ascending=False)
                                    
                                    # Highlight returns
                                    def highlight_pos_neg(val):
                                        try:
                                            color = 'rgba(0, 255, 0, 0.1)' if float(val) > 0 else 'rgba(255, 0, 0, 0.1)'
                                            return f'background-color: {color}'
                                        except:
                                            return ''
                                            
                                    st.dataframe(
                                        stock_summary_df.style.map(highlight_pos_neg, subset=["Cumulative Return [%]", "Total PnL ($)"]), 
                                        use_container_width=True
                                    )
                                    
                                    # Plotly Bar Chart comparing returns
                                    import plotly.express as px
                                    fig_stock = px.bar(
                                        stock_summary_df,
                                        x="Stock",
                                        y="Cumulative Return [%]",
                                        color="Cumulative Return [%]",
                                        color_continuous_scale=px.colors.diverging.RdYlGn,
                                        title="Asset Return Comparison under current Strategy",
                                        text_auto='.2f'
                                    )
                                    fig_stock.update_layout(
                                        plot_bgcolor='#0e1117',
                                        paper_bgcolor='#0e1117',
                                        font_color='white'
                                    )
                                    st.plotly_chart(fig_stock, use_container_width=True)

                            if "Cumulative Return [%]" in results_df.columns:
                                import plotly.express as px
                                st.markdown("---")
                                st.subheader("Return Distribution")
                                fig = px.histogram(
                                    results_df, 
                                    x="Cumulative Return [%]", 
                                    nbins=50, 
                                    title="Distribution of Strategy Cumulative Returns across intervals", 
                                    marginal="box", 
                                    color_discrete_sequence=['#00CC96']
                                )
                                st.plotly_chart(fig, use_container_width=True)

                            st.markdown("---")
                            st.subheader("Ranked Performance Matrix")

                            # Let user sort the dataframe easily
                            sort_col = st.selectbox("Sort By Metric:", results_df.columns, index=results_df.columns.get_loc("Cumulative Return [%]") if "Cumulative Return [%]" in results_df.columns else 0)
                            results_df = results_df.sort_values(by=sort_col, ascending=False)

                            def highlight_positive(val):
                                try:
                                    color = 'rgba(0, 255, 0, 0.1)' if float(val) > 0 else 'rgba(255, 0, 0, 0.1)'
                                    return f'background-color: {color}'
                                except:
                                    return ''

                            if "Cumulative Return [%]" in results_df.columns:
                                st.dataframe(results_df.style.map(highlight_positive, subset=["Cumulative Return [%]"]), use_container_width=True)
                            else:
                                st.dataframe(results_df, use_container_width=True)
                        else:
                            st.warning("All data slices were too small or failed to execute.")

                    except Exception as e:
                        st.error(f"Error during bulk testing: {e}")
                    finally:
                        st.session_state['bulk_running'] = False
                        if os.path.exists("stop_flag.txt"):
                            try: os.remove("stop_flag.txt")
                            except: pass

# --- TAB 4: Results & Analytics ---
if active_tab == "Results & Analytics":
    st.header("Results & Analytics Dashboard")
    st.write("Analyze and compare previous backtest runs and bulk tests saved in the `results/` directory.")
    
    # We consolidate results using tabs
    sub_tab1, sub_tab2 = st.tabs(["Run Performance & Comparison", "Bulk Portfolio Viewer"])
    
    results_dir = "results"
    
    with sub_tab1:
        st.subheader("Performance & Comparison")
        
        stats_files = []
        if os.path.exists(results_dir):
            stats_files = [f for f in os.listdir(results_dir) if f.endswith('_stats.csv') and not f.startswith('BULK_')]
            
        if not stats_files:
            st.info("No saved results found. Run a backtest in the previous tab to generate results.")
        else:
            run_names = [f.replace('_stats.csv', '') for f in stats_files]
            
            selected_runs = st.multiselect(
                "Select Runs to Analyze/Compare (Select 1 for dashboard, multiple for comparison):", 
                run_names, 
                default=[run_names[-1]] if run_names else None
            )
            
            if selected_runs:
                if len(selected_runs) == 1:
                    run = selected_runs[0]
                    stats_path = os.path.join(results_dir, f"{run}_stats.csv")
                    trades_path = os.path.join(results_dir, f"{run}_trades.csv")
                    plot_path = os.path.join(results_dir, f"{run}_plot.html")
                    
                    if os.path.exists(stats_path):
                        try:
                            stats_series = pd.read_csv(stats_path, index_col=0).iloc[:, 0]
                            trades_df = pd.read_csv(trades_path) if os.path.exists(trades_path) else pd.DataFrame()
                            metrics = calculate_strategy_metrics(stats_series, trades_df)
                            
                            mc_results = None
                            if not trades_df.empty and 'ReturnPct' in trades_df.columns:
                                returns = trades_df['ReturnPct'].values / 100.0
                                if len(returns) >= 5:
                                    start_cap = float(stats_series.get('Equity Start [$]', 10000.0))
                                    mc_results = run_monte_carlo_sim(returns, n_simulations=1000, confidence_level=95, start_capital=start_cap)
                                    
                            render_unified_dashboard(run, metrics, trades_df, plot_path, mc_results)
                        except Exception as e:
                            st.error(f"Error loading dashboard for {run}: {e}")
                else:
                    # Multiple runs selected: Side-by-Side Comparison
                    st.write(f"### Comparing {len(selected_runs)} Runs")
                    
                    comp_data = {}
                    for run in selected_runs:
                        stats_path = os.path.join(results_dir, f"{run}_stats.csv")
                        trades_path = os.path.join(results_dir, f"{run}_trades.csv")
                        
                        if os.path.exists(stats_path):
                            try:
                                stats_series = pd.read_csv(stats_path, index_col=0).iloc[:, 0]
                                trades_df = pd.read_csv(trades_path) if os.path.exists(trades_path) else pd.DataFrame()
                                metrics = calculate_strategy_metrics(stats_series, trades_df)
                                
                                mc_results = None
                                if not trades_df.empty and 'ReturnPct' in trades_df.columns:
                                    returns = trades_df['ReturnPct'].values / 100.0
                                    if len(returns) >= 5:
                                        start_cap = float(stats_series.get('Equity Start [$]', 10000.0))
                                        mc_results = run_monte_carlo_sim(returns, n_simulations=1000, confidence_level=95, start_capital=start_cap)
                                
                                comp_data[run] = {
                                    'CAGR (Ann. Return)': f"{metrics.get('Annualized Return [%]', 0.0):.2f}%",
                                    'Max Drawdown': f"{metrics.get('Max Drawdown [%]', 0.0):.2f}%",
                                    'Sharpe Ratio': f"{metrics.get('Sharpe Ratio', 0.0):.2f}",
                                    'Sortino Ratio': f"{metrics.get('Sortino Ratio', 0.0):.2f}",
                                    'Calmar Ratio': f"{metrics.get('Calmar Ratio', 0.0):.2f}",
                                    'Profit Factor': f"{metrics.get('Profit Factor', 0.0):.2f}",
                                    'Win Rate': f"{metrics.get('Win Rate [%]', 0.0):.2f}%",
                                    'P/L Ratio': f"{metrics.get('P/L Ratio', 0.0):.2f}",
                                    'Expectancy': f"{metrics.get('Expectancy [%]', 0.0):.4f}%",
                                    'Total Trades': int(metrics.get('Total Trades', 0)),
                                    'Simulated Median Drawdown': f"{mc_results['median_max_drawdown']:.2f}%" if mc_results else 'N/A',
                                    'Simulated 95% VaR Drawdown': f"{mc_results['var_max_drawdown']:.2f}%" if mc_results else 'N/A'
                                }
                            except Exception as e:
                                st.warning(f"Could not load stats for {run}: {e}")
                                
                    if comp_data:
                        comparison_df = pd.DataFrame(comp_data)
                        st.dataframe(comparison_df, use_container_width=True)
                        
                        st.markdown("---")
                        st.write("### Interactive Charts Comparison")
                        chart_tabs = st.tabs(selected_runs)
                        for idx, run in enumerate(selected_runs):
                            with chart_tabs[idx]:
                                plot_path = os.path.join(results_dir, f"{run}_plot.html")
                                if os.path.exists(plot_path):
                                    with open(plot_path, "r", encoding='utf-8') as f:
                                        html_content = f.read()
                                        components.html(html_content, height=600, scrolling=True)
                                else:
                                    st.warning(f"No interactive chart found for {run}.")
                                    
                        st.markdown("---")
                        st.write("### Monte Carlo Risk Comparison")
                        mc_tabs = st.tabs([f"MC: {run}" for run in selected_runs])
                        for idx, run in enumerate(selected_runs):
                            with mc_tabs[idx]:
                                trades_path = os.path.join(results_dir, f"{run}_trades.csv")
                                stats_path = os.path.join(results_dir, f"{run}_stats.csv")
                                trades_df = pd.read_csv(trades_path) if os.path.exists(trades_path) else pd.DataFrame()
                                stats_series = pd.read_csv(stats_path, index_col=0).iloc[:, 0] if os.path.exists(stats_path) else pd.Series()
                                
                                if not trades_df.empty and 'ReturnPct' in trades_df.columns:
                                    returns = trades_df['ReturnPct'].values / 100.0
                                    if len(returns) >= 5:
                                        start_cap = float(stats_series.get('Equity Start [$]', 10000.0))
                                        mc_results = run_monte_carlo_sim(returns, n_simulations=1000, confidence_level=95, start_capital=start_cap)
                                        
                                        if mc_results:
                                            mcol1, mcol2 = st.columns([3, 2])
                                            with mcol1:
                                                n_sim = len(mc_results['max_dds'])
                                                all_eq_curves = mc_results['curves']
                                                sample_idx = np.random.choice(range(n_sim), min(50, n_sim), replace=False)
                                                
                                                from bokeh.plotting import figure
                                                from bokeh.models import NumeralTickFormatter
                                                from bokeh.embed import file_html
                                                from bokeh.resources import CDN
                                                
                                                p_mc = figure(title=f"Simulated Equity Paths - {run}", 
                                                              x_axis_label='Trade Number', 
                                                              y_axis_label='Equity ($)',
                                                              tools="pan,box_zoom,reset,save",
                                                              active_drag="box_zoom",
                                                              height=350,
                                                              sizing_mode="stretch_width")
                                                
                                                p_mc.background_fill_color = "#0e1117"
                                                p_mc.border_fill_color = "#0e1117"
                                                p_mc.title.text_color = "white"
                                                p_mc.xaxis.axis_label_text_color = "white"
                                                p_mc.yaxis.axis_label_text_color = "white"
                                                p_mc.xaxis.major_label_text_color = "white"
                                                p_mc.yaxis.major_label_text_color = "white"
                                                p_mc.grid.grid_line_color = "#333333"
                                                
                                                n_points = len(all_eq_curves[0])
                                                if n_points > 500:
                                                    plot_indices = np.linspace(0, n_points - 1, 500, dtype=int)
                                                else:
                                                    plot_indices = np.arange(n_points)

                                                for s_idx in sample_idx:
                                                    curve = all_eq_curves[s_idx]
                                                    p_mc.line(list(plot_indices), list(curve[plot_indices] if n_points > 500 else curve), line_width=1, alpha=0.3, color="gray")
                                                    
                                                avg_curve = np.mean(all_eq_curves, axis=0)
                                                p_mc.line(list(plot_indices), list(avg_curve[plot_indices] if n_points > 500 else avg_curve), line_width=4, color="#00d4ff", legend_label="Average Path")
                                                
                                                p_mc.yaxis.formatter = NumeralTickFormatter(format="$0,0")
                                                p_mc.legend.location = "top_left"
                                                p_mc.legend.background_fill_color = "#0e1117"
                                                p_mc.legend.label_text_color = "white"
                                                p_mc.legend.background_fill_alpha = 0.8
                                                
                                                mc_html = file_html(p_mc, CDN, "Monte Carlo Spaghetti Plot")
                                                components.html(mc_html, height=380)
                                                
                                            with mcol2:
                                                st.metric("Expected Final Equity", f"${mc_results['expected_final_equity']:,.2f}")
                                                st.metric("Median Simulated Drawdown", f"{mc_results['median_max_drawdown']:.2f}%")
                                                st.metric("95% Probable Max DD (VaR)", f"{mc_results['var_max_drawdown']:.2f}%")
                                                
                                                counts, bin_edges = np.histogram(mc_results['max_dds'], bins=20)
                                                bin_labels = [f"{x:.1f}%" for x in bin_edges[:-1]]
                                                hist_df = pd.DataFrame({'Count': counts}, index=bin_labels)
                                                st.bar_chart(hist_df, use_container_width=True)
                                    else:
                                        st.warning(f"Not enough trades ({len(returns)}) for Monte Carlo on {run}.")
                                else:
                                    st.warning(f"No trades recorded for {run}.")
    
    with sub_tab2:
        st.subheader("Bulk Portfolio & Matrix Viewer")
        
        bulk_files = []
        if os.path.exists(results_dir):
            bulk_files = [f for f in os.listdir(results_dir) if f.startswith('BULK_') and f.endswith('_stats.csv')]
            
        if not bulk_files:
            st.info("No saved bulk results found. Run a bulk test in the Bulk Testing tab to generate results.")
        else:
            bulk_run_names = [f.replace('_stats.csv', '') for f in bulk_files]
            selected_bulk_run = st.selectbox("Select Bulk Test Run:", bulk_run_names)
            
            if selected_bulk_run:
                try:
                    results_df = pd.read_csv(os.path.join(results_dir, f"{selected_bulk_run}_stats.csv"), index_col=0)
                    trades_file_path = os.path.join(results_dir, f"{selected_bulk_run}_trades.csv")
                    combined_trades_df = pd.read_csv(trades_file_path) if os.path.exists(trades_file_path) else pd.DataFrame()
                    
                    if not combined_trades_df.empty:
                        st.markdown("### Combined Portfolio Performance")
                        st.write("Aggregated metrics treating all bulk intervals as a single unified portfolio.")
                        
                        # We calculate metrics for the combined trade ledger
                        port_metrics = calculate_strategy_metrics({}, combined_trades_df)
                        
                        # Run Portfolio Monte Carlo
                        p_mc_results = None
                        if 'ReturnPct' in combined_trades_df.columns:
                            returns = combined_trades_df['ReturnPct'].values / 100.0
                            if len(returns) >= 5:
                                p_mc_results = run_monte_carlo_sim(returns, n_simulations=1000, confidence_level=95, start_capital=10000) # default cap
                        
                        pm1, pm2, pm3, pm4 = st.columns(4)
                        pm1.metric("Combined Profit Factor", f"{port_metrics['Profit Factor']:.2f}")
                        pm2.metric("Combined Win Rate", f"{port_metrics['Win Rate [%]']:.2f}%")
                        pm3.metric("Combined Expectancy", f"{port_metrics['Expectancy [%]']:.4f}%")
                        pm4.metric("Total Portfolio Trades", f"{port_metrics['Total Trades']}")
                        
                        if p_mc_results:
                            with st.expander("Portfolio Monte Carlo Analysis", expanded=False):
                                st.write(f"Expected Portfolio Final Equity: **${p_mc_results['expected_final_equity']:,.2f}**")
                                st.write(f"Portfolio Median Drawdown: **{p_mc_results['median_max_drawdown']:.2f}%**")
                                st.write(f"Portfolio 95% Value-at-Risk (VaR) Drawdown: **{p_mc_results['var_max_drawdown']:.2f}%**")
                                
                                # Plot portfolio histogram
                                counts, bin_edges = np.histogram(p_mc_results['max_dds'], bins=20)
                                bin_labels = [f"{x:.1f}%" for x in bin_edges[:-1]]
                                port_hist_df = pd.DataFrame({
                                    'Count': counts
                                }, index=bin_labels)
                                st.bar_chart(port_hist_df, use_container_width=True)
                        
                        if "Cumulative Return [%]" in results_df.columns:
                            import plotly.express as px
                            st.markdown("---")
                            st.subheader("Return Distribution")
                            fig = px.histogram(
                                results_df, 
                                x="Cumulative Return [%]", 
                                nbins=50, 
                                title="Distribution of Strategy Cumulative Returns across intervals", 
                                marginal="box", 
                                color_discrete_sequence=['#00CC96']
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                        st.markdown("---")
                        st.subheader("Ranked Performance Matrix")
                        
                        sort_col = st.selectbox("Sort By Metric:", results_df.columns, index=results_df.columns.get_loc("Cumulative Return [%]") if "Cumulative Return [%]" in results_df.columns else 0, key="bulk_viewer_sort_col")
                        sorted_results_df = results_df.sort_values(by=sort_col, ascending=False)
                        
                        def highlight_positive(val):
                            try:
                                color = 'rgba(0, 255, 0, 0.1)' if float(val) > 0 else 'rgba(255, 0, 0, 0.1)'
                                return f'background-color: {color}'
                            except:
                                return ''
                                
                        if "Cumulative Return [%]" in sorted_results_df.columns:
                            st.dataframe(sorted_results_df.style.map(highlight_positive, subset=["Cumulative Return [%]"]), use_container_width=True)
                        else:
                            st.dataframe(sorted_results_df, use_container_width=True)
                    else:
                        st.warning("No combined trade ledger found for this bulk run.")
                except Exception as e:
                    st.error(f"Error loading bulk results: {e}")

# --- TAB 6: Optimize Parameters ---
if active_tab == "Optimize Parameters":
    st.header("Parameter Optimization Engine")
    st.write("Automatically brute-force massive combinations of parameter ranges to find the optimal strategy variables.")

    o_col1, o_col2 = st.columns(2)
    with o_col1:
        data_dir = "data"
        data_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')] if os.path.exists(data_dir) else []
        selected_opt_data = st.selectbox("Select Dataset", data_files, key="opt_data")
        
        # --- Date Slicer UI (from Tab 3) ---
        if selected_opt_data:
            try:
                df_preview = pd.read_csv(os.path.join(data_dir, selected_opt_data))
                df_preview.columns = df_preview.columns.str.strip()
                dt_col = None
                for col in df_preview.columns:
                    if col.lower() in ['date', 'time', 'datetime', 'timestamp']:
                        dt_col = col
                        break
                if dt_col:
                    df_preview[dt_col] = pd.to_datetime(df_preview[dt_col], format='mixed')
                    min_date = df_preview[dt_col].min().date()
                    max_date = df_preview[dt_col].max().date()
                    
                    st.write(f"Available from **{min_date}** to **{max_date}**")
                    
                    st.markdown("**Filter Data Range**")
                    d_col1, d_col2 = st.columns(2)
                    
                    import datetime
                    with d_col1:
                        start_d = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key="o_sd")
                        start_t = st.time_input("Start Time", value=datetime.time(0, 0), key="o_st")
                    with d_col2:
                        end_d = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key="o_ed")
                        end_t = st.time_input("End Time", value=datetime.time(23, 59), key="o_et")
                        
                    start_datetime_opt = datetime.datetime.combine(start_d, start_t)
                    end_datetime_opt = datetime.datetime.combine(end_d, end_t)
                    
                else:
                    start_datetime_opt, end_datetime_opt = None, None
            except Exception as e:
                start_datetime_opt, end_datetime_opt = None, None
                st.warning(f"Could not load dates for preview: {e}")
        else:
            start_datetime_opt, end_datetime_opt = None, None
            
    with o_col2:
        strategies_dir = "strategies"
        strategy_files = [f for f in os.listdir(strategies_dir) if f.endswith('.py')] if os.path.exists(strategies_dir) else []
        selected_opt_strat = st.selectbox("Select Strategy", strategy_files, key="opt_strat")

    st.markdown("---")
    
    if selected_opt_strat:
        # Load strat to parse attributes
        strat_class = load_strategy(os.path.join(strategies_dir, selected_opt_strat))
        if strat_class:
            st.subheader("1. Tune Parameters")
            
            # Introspect for class-level int/float attributes (excluding dunders)
            tunable_params = {}
            for key in dir(strat_class):
                if not key.startswith('_'): # Skip internal attributes
                    val = getattr(strat_class, key)
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        tunable_params[key] = val
            
            if not tunable_params:
                st.warning("No tunable parameters (Integers/Floats) found in this Strategy class.")
            else:
                st.write(f"Detected {len(tunable_params)} tunable variables inside `{strat_class.__name__}`.")
                
                # Build dynamic constraint UI
                opt_ranges = {}
                for param, default_val in tunable_params.items():
                    with st.expander(f"Variable: `{param}` (Default: {default_val})", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        is_float = isinstance(default_val, float)
                        step_val = 0.1 if is_float else 1
                        
                        min_val = c1.number_input(f"Min", value=float(default_val) if is_float else int(default_val), key=f"min_{param}")
                        max_val = c2.number_input(f"Max", value=float(default_val)*2 if is_float else int(default_val)*2, key=f"max_{param}")
                        step = c3.number_input(f"Step", value=step_val, key=f"step_{param}", format="%.4f" if is_float else None)
                        
                        # Generate python range array or np.arange for floats
                        if min_val >= max_val:
                            st.warning(f"Min must be smaller than Max for {param}")
                        else:
                            import numpy as np
                            # Generate the array of values to test
                            val_range = np.arange(min_val, max_val + step, step)
                            if not is_float:
                                val_range = [int(v) for v in val_range] # ensure ints
                            opt_ranges[param] = list(val_range)
                            st.caption(f"Testing {len(opt_ranges[param])} values: from {min_val} to {max_val}")

                st.subheader("2. Optimization Rules")
                r_col1, r_col2, r_col3 = st.columns(3)
                with r_col1:
                    maximize_opt = st.selectbox("Maximize Metric:", ["Return [%]", "Sharpe Ratio", "Sortino Ratio", "Win Rate [%]", "Equity Final [$]"])
                with r_col2:
                    opt_method = st.selectbox("Optimization Method:", ["Grid Search (Brute Force)", "SMBO (sambo)"], help="'SMBO' uses Machine Learning algorithms to search constraints faster. Requires sambo package.")
                with r_col3:
                    max_skopt_tries = st.number_input("Max Tries (SMBO only)", value=200, step=50, help="Max iterations for SMBO to prevent infinite hanging.")
                
                st.markdown("---")
                st.markdown("**(Uses the Advanced Parameters currently set in Tab 3 `Run Backtest` for capital/margins/etc)**")
                
                if st.button("Run Optimization", type="primary", use_container_width=True):
                    if not opt_ranges:
                        st.error("You must define valid ranges before optimizing.")
                    else:
                        st.info("Note: To forcefully stop a long optimization, use the Stop Server button in the sidebar.")
                        with st.spinner(f"Running {opt_method}... this may take a moment depending on range sizes!"):
                            try:
                                # 1. Prepare Data
                                df = pd.read_csv(os.path.join(data_dir, selected_opt_data))
                                df.columns = df.columns.str.strip()
                                col_map = {c.lower(): c.capitalize() for c in df.columns}
                                df.rename(columns=col_map, inplace=True)
                                if 'Volume' not in df.columns and 'volume' in col_map: 
                                    df.rename(columns={'volume': 'Volume'}, inplace=True)
                                
                                dt_col = next((c for c in df.columns if c.lower() in ['date', 'time', 'datetime', 'timestamp', 'unnamed: 0']), None)
                                df[dt_col] = pd.to_datetime(df[dt_col], format='mixed')
                                df.set_index(dt_col, inplace=True)
                                if df.index.tz is not None:
                                    df.index = df.index.tz_localize(None)
                                df.sort_index(inplace=True)
                                
                                # Apply DateTime Slicing
                                if start_datetime_opt and end_datetime_opt:
                                    try:
                                        start_dt_pd = pd.to_datetime(start_datetime_opt)
                                        end_dt_pd = pd.to_datetime(end_datetime_opt)
                                        mask = (df.index >= start_dt_pd) & (df.index <= end_dt_pd)
                                        df = df.loc[mask]
                                        if df.empty:
                                            st.error("DateTime slice resulted in an empty dataset. Please broaden the range.")
                                            st.stop()
                                    except Exception as e:
                                        st.warning(f"Error applying datetime slice: {e}. Running on full dataset.")
                                
                                # Apply Timeframe Resampling
                                if resample_tf != "No Resampling (Use Native)":
                                    tf_map = {
                                        "5 Min ('5T')": "5T",
                                        "15 Min ('15T')": "15T",
                                        "30 Min ('30T')": "30T",
                                        "1 Hour ('1H')": "1H",
                                        "4 Hours ('4H')": "4H",
                                        "1 Day ('1D')": "1D"
                                    }
                                    rule = tf_map.get(resample_tf)
                                    if rule:
                                        try:
                                            resample_dict = {}
                                            if 'Open' in df.columns: resample_dict['Open'] = 'first'
                                            if 'High' in df.columns: resample_dict['High'] = 'max'
                                            if 'Low' in df.columns: resample_dict['Low'] = 'min'
                                            if 'Close' in df.columns: resample_dict['Close'] = 'last'
                                            if 'Volume' in df.columns: resample_dict['Volume'] = 'sum'
                                            for col in df.columns:
                                                if col not in resample_dict:
                                                    resample_dict[col] = 'first'
                                            df = df.resample(rule).agg(resample_dict).dropna()
                                            st.info(f"Resampled dataset to `{rule}` timeframe. New shape: {df.shape}")
                                        except Exception as resample_err:
                                            st.warning(f"Failed to resample: {resample_err}. Running on native data.")
                                
                                # 2. Prepare Engine
                                bt = Backtest(
                                    df, 
                                    strat_class, 
                                    cash=init_cash,
                                    commission=commission, 
                                    spread=spread,
                                    margin=margin,
                                    trade_on_close=trade_on_close,
                                    hedging=hedging,
                                    exclusive_orders=exclusive_orders,
                                    finalize_trades=finalize_trades
                                )
                                
                                # 3. Optimize
                                method_arg = 'sambo' if 'SMBO' in opt_method else 'grid'
                                from backtesting.lib import plot_heatmaps
                                
                                kw_args = {**opt_ranges, 'maximize': maximize_opt, 'return_heatmap': True, 'method': method_arg}
                                
                                if method_arg == 'sambo':
                                    kw_args['max_tries'] = int(max_skopt_tries)
                                
                                stats, heatmap = bt.optimize(**kw_args)
                                
                                # 4. Render Outcomes
                                st.success("Optimization Complete!")
                                
                                col_res1, col_res2 = st.columns(2)
                                with col_res1:
                                    st.write("### Winning Parameters")
                                    # Stats._strategy contains the instantiated strategy with the optimized params
                                    best_strat = stats['_strategy']
                                    st.code(str(best_strat))
                                    
                                with col_res2:
                                    st.write("### Top Performances")
                                    # Heatmap is a pandas series with a MultiIndex of the params
                                    # Sort it to show the top 10 parameter combos
                                    top_10 = heatmap.sort_values(ascending=False).head(10)
                                    st.dataframe(top_10, use_container_width=True)
                                
                                st.write("### Final Statistics")
                                stats_clean = stats.drop(['_strategy', '_equity_curve', '_trades'])
                                st.dataframe(pd.DataFrame(stats_clean, columns=["Value"]).astype(str), use_container_width=True)
                                
                                # 5. Auto Save to dedicated folder
                                timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
                                report_name = f"OPT_{method_arg}_{selected_opt_strat.replace('.py', '')}_{selected_opt_data.replace('.csv', '')}_{timestamp}"
                                
                                opt_dir = "opt_results"
                                if not os.path.exists(opt_dir): os.makedirs(opt_dir)
                                
                                # Save Dataframes natively
                                try:
                                    stats_clean.to_csv(os.path.join(opt_dir, f"{report_name}_stats.csv"))
                                    heatmap.to_csv(os.path.join(opt_dir, f"{report_name}_heatmap.csv"))
                                    st.info(f"Metrics saved to `{opt_dir}/` directory.")
                                except Exception as save_err:
                                    st.warning(f"Could not save output data to CSVs: {save_err}")
                                
                                # Save Plot natively
                                plot_file = os.path.join(opt_dir, f"{report_name}_plot.html")
                                has_plot = False
                                if len(df) <= 10000:
                                    try:
                                        bt.plot(filename=plot_file, open_browser=False, resample=False)
                                        has_plot = True
                                    except Exception as plot_err:
                                        st.warning(f"Could not generate interactive plot: {plot_err}")
                                else:
                                    st.info("Winning strategy interactive chart disabled for datasets > 10,000 rows to prevent browser lagging.")
                                
                                # Save Heatmaps natively
                                heatmap_file = os.path.join(opt_dir, f"{report_name}_heatmap.html")
                                try:
                                    plot_heatmaps(heatmap, agg='max', filename=heatmap_file, open_browser=False)
                                except Exception as heatmap_err:
                                    st.warning(f"Could not generate interactive heatmap: {heatmap_err}")
                                
                                if has_plot and os.path.exists(plot_file):
                                    st.subheader("Winning Strategy Chart")
                                    with open(plot_file, "r", encoding='utf-8') as f:
                                        html_content = f.read()
                                        components.html(html_content, height=800, scrolling=True)
                                    
                                if os.path.exists(heatmap_file):
                                    st.markdown("---")
                                    st.subheader("Parameter Landscape Heatmaps")
                                    st.write("Hover over the cells to explore the multi-dimensional parameter performance.")
                                    with open(heatmap_file, "r", encoding='utf-8') as f:
                                        hm_content = f.read()
                                        components.html(hm_content, height=1000, scrolling=True)
                                    
                            except Exception as e:
                                st.error(f"Optimization failed: {e}")


# --- TAB 7: Paper Trading ---
if active_tab == "Paper Trading":
    st.header("Paper Trading Engine")
    st.write("Run your strategy on live-updating data natively in the background. You can navigate away from this tab while engines run.")
    
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    state_files = [f for f in os.listdir(results_dir) if f.startswith('pt_state_') and f.endswith('.json')]
    
    # 1. Start New Engine Form
    with st.expander("Launch New Engine", expanded=len(state_files) == 0):
        col1, col2 = st.columns(2)
        with col1:
            pt_source_opt = st.selectbox("Live Data Source", ["TradingView", "Yahoo Finance"], key="pt_source")
            pt_symbol = st.text_input("Symbol", value="SBIN", key="pt_sym").upper()
            pt_exchange = st.text_input("Exchange (TradingView only)", value="NSE", key="pt_ex").upper()
            
            if pt_source_opt == "TradingView":
                tv_options = ['in_1_minute', 'in_3_minute', 'in_5_minute', 'in_15_minute', 'in_30_minute', 'in_45_minute', 
                              'in_1_hour', 'in_2_hour', 'in_3_hour', 'in_4_hour', 'in_daily', 'in_weekly', 'in_monthly']
                pt_interval = st.selectbox("Interval", tv_options, index=0, key="pt_int_tv")
            else:
                yf_options = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo']
                pt_interval = st.selectbox("Interval", yf_options, index=0, key="pt_int_yf")
                
        with col2:
            strategies_dir = "strategies"
            strategy_files = [f for f in os.listdir(strategies_dir) if f.endswith('.py')] if os.path.exists(strategies_dir) else []
            selected_pt_strat = st.selectbox("Strategy File", strategy_files, key="pt_strat")
            
            pt_init_cash = st.number_input("Initial Cash", min_value=1, value=10000, step=1000, key="pt_cash")
            pt_commission = st.number_input("Commission (e.g., 0.002 = 0.2%)", min_value=0.0, max_value=0.1, value=0.0, step=0.001, format="%.4f", key="pt_comm")
            pt_poll_delay = st.slider("Poll Delay (Seconds)", min_value=3, max_value=86400, value=60, help="How often the daemon fetches new data (e.g., 3600 = Hourly, 86400 = Daily).", key="pt_delay")
    
        if st.button("Start Engine", type="primary"):
            if not selected_pt_strat:
                st.error("Please select a valid strategy.")
            else:
                strat_path = os.path.abspath(os.path.join(strategies_dir, selected_pt_strat))
                import subprocess
                cmd = [
                    sys.executable, "paper_engine.py",
                    "--source", pt_source_opt,
                    "--symbol", pt_symbol,
                    "--exchange", pt_exchange,
                    "--interval", pt_interval,
                    "--strategy", strat_path,
                    "--cash", str(pt_init_cash),
                    "--commission", str(pt_commission),
                    "--delay", str(pt_poll_delay)
                ]
                try:
                    subprocess.Popen(cmd)
                    st.success(f"Successfully launched background paper trading engine for `{pt_symbol}`.")
                    time.sleep(1) # wait a moment for the JSON to be written
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to start daemon: {e}")

    st.divider()
    
    # 2. Active Dashboards
    st.subheader("Active Engines")
    
    col_ref, col_spacer = st.columns([1, 5])
    if col_ref.button("Refresh"):
        st.rerun()
        
    if not state_files:
        st.info("No active paper trading engines found.")
    else:
        for sf in state_files:
            sym = sf.replace('pt_state_', '').replace('.json', '')
            state_path = os.path.join(results_dir, sf)
            
            try:
                import json
                with open(state_path, 'r') as f:
                    state = json.load(f)
            except Exception as e:
                st.warning(f"Could not read state for {sym}: {e}")
                continue
                
            status_color = "[ON]" if state.get("status") in ["Running", "Starting"] else "[OFF]"
            if state.get("status") == "Error":
                status_color = "[ERR]"
                
            with st.container(border=True):
                st.markdown(f"#### {status_color} {sym} | Backend: {state.get('status')} | Last Update: `{state.get('last_updated', 'N/A')}`")
                
                if state.get("error"):
                    st.error(state["error"])
                    
                metrics = state.get("metrics")
                if metrics:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Latest Close", f"${metrics['last_price']:.2f}", f"Bar Time: {metrics['last_time']}")
                    m2.metric("Net Equity", f"${metrics['curr_equity']:,.2f}", f"{metrics['return_pct']:.2f}%")
                    m3.metric("Pos Status", metrics['open_pos'])
                    m4.metric("Active Trade", metrics['pos_info'])
                    
                with st.expander("Recent Executions"):
                    trades = state.get("recent_trades", [])
                    if trades:
                        st.dataframe(pd.DataFrame(trades), use_container_width=True)
                    else:
                        st.write("No trades executed yet.")
                        
                plot_file = os.path.join(results_dir, f"pt_plot_{sym}.html")
                if os.path.exists(plot_file):
                    with st.expander("Live Interactive Chart"):
                        try:
                            with open(plot_file, "r", encoding='utf-8') as f:
                                html_content = f.read()
                                components.html(html_content, height=650, scrolling=True)
                        except Exception as e:
                            st.warning(f"Could not load chart: {e}")
                            
                c_stop, c_del = st.columns([2, 8])
                if c_stop.button(f"Stop `{sym}` Engine", key=f"stop_{sym}"):
                    stop_path = os.path.join(results_dir, f"pt_stop_{sym}.txt")
                    with open(stop_path, 'w') as f:
                        f.write("STOP")
                    st.success(f"Signal sent to gracefully stop {sym}. It will shutdown on its next loop.")
                    time.sleep(1)
                    st.rerun()
                
                # Option to clear disconnected/stopped engines from dashboard
                if state.get("status") in ["Stopped", "Error"]:
                    if c_del.button(f"Remove `{sym}` from Dashboard", key=f"del_{sym}"):
                        os.remove(state_path)
                        st.rerun()


