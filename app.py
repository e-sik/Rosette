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
purge_old_files([LOG_DIR, "data", "results", "bulk_results", "opt_results"], days=7)

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
st.set_page_config(page_title="Rosette 🌌 | Quantitative Finance", layout="wide", page_icon="🌌")

# Main Header with Logo
col_title, col_logo = st.columns([8, 1])
with col_title:
    st.title("Rosette: Algorithmic Trading Workspace")
with col_logo:
    try:
        st.image("assets/rosette_logo.png", use_container_width=True)
    except Exception:
        pass

# --- Sidebar ---
try:
    st.sidebar.image("assets/rosette_banner.png", use_container_width=True)
except Exception:
    pass

st.sidebar.header("🚀 Rosette Control Panel")
if st.sidebar.button("🛑 Stop Local Server", type="primary", use_container_width=True, help="Click to shut down the Streamlit server. You will need to use your terminal to start it again."):
    st.sidebar.warning("Shutting down the server...")
    logger.info("Server stopped manually via sidebar button.")
    os._exit(0)

st.sidebar.divider()
st.sidebar.info("📦 **Data Archival Policy**\n\nTo ensure peak performance, all Data, Backtest Results, and interactive Charts are automatically pruned and deleted after **7 Days** of inactivity.")
st.sidebar.caption("SaaS Community Edition")

# --- Initialize Session State ---
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

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(["📊 Fetch Data", "📝 Strategy Editor", "⚙️ Run Backtest", "📈 Compare Results", "🔄 Bulk Testing", "🎯 Optimize Parameters", "⏱️ Paper Trading", "🎲 Monte Carlo Analysis"])

# --- TAB 1: Data Fetching ---
with tab1:
    st.header("Fetch Historical Data")
    st.write("Download historical data directly from TradingView or Yahoo Finance.")
    
    st.info("""
    **API Limitations Reminder:**
    * **Yahoo Finance**: Excellent for 10+ years of Daily/Weekly data. Strictly limits `1m` intraday to the last 7 days, and `5m-90m` to the last 60 days.
    * **TradingView**: No specific date limits, but hard-caps the total number of historical candles out put to ~5,000 per request.
    """)
    
    data_source_opt = st.selectbox("Data Source", ["TradingView", "Yahoo Finance"], help="TradingView is great for standard symbols. Yahoo Finance is better for very deep historical backtesting (10+ years).")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Symbol", value="SBIN").upper()
        if data_source_opt == "Yahoo Finance":
            st.caption("Tip: Add `.NS` for NSE stocks (e.g. SBIN.NS) or `.BO` for BSE.")
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
    else:
        st.caption("Note: Yahoo Finance limits intraday (1m, 5m, 1h) searches to the last 30-70 days, but has unlimited Daily/Weekly history.")
    
    if st.button("Fetch Data", type="primary"):
        with st.spinner(f"Fetching {symbol} from {start_date_fetch} to {end_date_fetch} via {data_source_opt}..."):
            try:
                from tvDatafeed import Interval
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
                st.success(f"✅ Data Quality Check Passed! 0 missing values or zero-volume anomalies found in `{os.path.basename(fp)}`. You are ready to backtest.")
            else:
                st.warning(f"⚠️ **Data Quality Issues Detected in `{os.path.basename(fp)}`!**\n\nFound {total_nans} missing (NaN) values and {zero_vols} zero-volume rows.")
                
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
with tab2:
    st.header("📝 Strategy IDE Editor")
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
        st.markdown("#### 🛠️ IDE Configuration")
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
        st.markdown("#### 💻 Source Code")
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
            test_btn = st.button("🧪 Compile & Test Strategy", use_container_width=True)
        with btn_col2:
            save_btn = st.button("💾 Save Strategy Code", type="primary", use_container_width=True)
            
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
        st.subheader("🖥️ IDE Diagnostics Console")
        
        # Status Badges
        c1, c2, c3 = st.columns(3)
        
        def render_indicator(name, step_data):
            status = step_data["status"]
            if status == "Passed":
                st.success(f"✅ {name}: Passed")
            elif status == "Failed":
                st.error(f"❌ {name}: Failed")
            else:
                st.info(f"⚪ {name}: Pending")
                
        with c1:
            render_indicator("Syntax Compiler Check", diag["syntax"])
        with c2:
            render_indicator("Strategy Subclass & Method Check", diag["structure"])
        with c3:
            render_indicator("Mock execution (200 Days Dry-Run)", diag["dry_run"])
            
        # Failure Traceback / Console Log
        if not diag["success"]:
            st.markdown("### 🛑 Compilation & Runtime Diagnostics")
            for step in ["syntax", "structure", "dry_run"]:
                if diag[step]["status"] == "Failed":
                    st.error(f"Error in step: **{step.replace('_', ' ').title()}**")
                    st.code(diag[step]["msg"], language="text")
        else:
            st.success("🎉 Excellent! Your trading strategy is 100% syntactically correct and passed the mock backtest simulator execution with 0 errors. It is ready for historical backtesting.")

# --- TAB 3: Run Backtest ---
with tab3:
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
    
    default_exec_code = """
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
"""
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
        if st.button("🔄 Reset Script to Default"):
            st.session_state['exec_code_state'] = default_exec_code.strip()
            st.rerun()
    
    if st.button("▶ Run Script", type="primary", use_container_width=True):
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
                        if col.lower() in ['date', 'time', 'datetime', 'timestamp']:
                            datetime_col = col
                            break
                            
                    if datetime_col:
                        # Auto-parse arbitrary datetime formats (e.g. 8/19/2004)
                        df[datetime_col] = pd.to_datetime(df[datetime_col], format='mixed')
                        df.set_index(datetime_col, inplace=True)
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
                    exec(exec_code, {}, local_context)
                    
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
                    
                    # 4. Display Results
                    st.subheader("Performance Metrics")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Return", f"{stats['Return [%]']:.2f}%")
                    m2.metric("Final Equity", f"${stats['Equity Final [$]']:,.2f}")
                    m3.metric("Max Drawdown", f"{stats['Max. Drawdown [%]']:.2f}%")
                    m4.metric("Win Rate", f"{stats['Win Rate [%]']:.2f}%")
                    
                    with st.expander("View Full Statistics Table"):
                        st.dataframe(stats.drop(['_strategy', '_equity_curve', '_trades']).astype(str))
                        
                    if '_trades' in stats and not stats['_trades'].empty:
                        with st.expander("📝 View Trade History Ledger"):
                            st.dataframe(stats['_trades'], use_container_width=True)
                        
                    # Save results to disk automatically
                    import datetime
                    if not os.path.exists("results"):
                        os.makedirs("results")
                        
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    report_name = f"{selected_strategy_file.replace('.py', '')}_{selected_data.replace('.csv', '')}_{timestamp}"
                    
                    # Save stats
                    stats_file = os.path.join("results", f"{report_name}_stats.csv")
                    stats.drop(['_strategy', '_equity_curve', '_trades']).to_csv(stats_file)
                    st.success(f"Stats saved to `results/{os.path.basename(stats_file)}`")
                    
                    # Save trades
                    trades_file = os.path.join("results", f"{report_name}_trades.csv")
                    if '_trades' in stats and not stats['_trades'].empty:
                        stats['_trades'].to_csv(trades_file, index=False)
                        st.success(f"Trades saved to `results/{os.path.basename(trades_file)}`")
                        
                    # 5. Alpha Comparison
                    st.subheader("Benchmark Alpha Comparison")
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
                            
                            # Drop any NaNs from the very beginning if benchmark started later than strategy (rare)
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
                                    st.line_chart(alpha_df, use_container_width=True)
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
                        
                    # 6. Plot rendering
                    st.subheader("Interactive Chart")
                    plot_file = os.path.abspath(os.path.join("results", f"{report_name}_plot.html"))
                    
                    if bt is not None:
                        # Temporarily redirect bokeh output so streamlit can render the generated HTML
                        bt.plot(filename=plot_file, open_browser=False)
                        
                        with open(plot_file, "r", encoding='utf-8') as f:
                            html_content = f.read()
                            components.html(html_content, height=700, scrolling=True)
                        st.success(f"Chart saved to `results/{os.path.basename(plot_file)}`")
                    else:
                        st.warning("No interactive chart available (`bt` object missing).")
                        
                except Exception as e:
                    st.error(f"Error during backtest: {e}")
        else:
            st.error("Please select both a dataset and a strategy.")

# --- TAB 4: Compare Results ---
with tab4:
    st.header("Compare Historical Results")
    st.write("Analyze and compare previous backtest runs saved in the `results/` directory.")
    
    results_dir = "results"
    stats_files = []
    if os.path.exists(results_dir):
        stats_files = [f for f in os.listdir(results_dir) if f.endswith('_stats.csv')]
        
    if not stats_files:
        st.info("No saved results found. Run a backtest in the previous tab to generate results.")
    else:
        # Extract base run names (remove '_stats.csv')
        run_names = [f.replace('_stats.csv', '') for f in stats_files]
        
        selected_runs = st.multiselect("Select Runs to Compare:", run_names, default=[run_names[-1]] if run_names else None)
        
        if selected_runs:
            st.subheader("Performance Comparison")
            
            # Build comparative dataframe
            comparison_df = pd.DataFrame()
            for run in selected_runs:
                stats_path = os.path.join(results_dir, f"{run}_stats.csv")
                try:
                    # Read the CSV. The first column usually contains the metric names.
                    run_df = pd.read_csv(stats_path, index_col=0)
                    
                    # Ensure we are only grabbing the first data column if it parsed weirdly, and rename it to the run name
                    if len(run_df.columns) > 0:
                        series = run_df.iloc[:, 0]
                        series.name = run
                        comparison_df = pd.concat([comparison_df, series], axis=1)
                except Exception as e:
                    st.warning(f"Could not load stats for {run}: {e}")
            
            if not comparison_df.empty:
                # Transpose for easier reading if there are many metrics, or keep it vertical. 
                # Vertical side-by-side relies on Streamlit's full width.
                st.dataframe(comparison_df.astype(str), use_container_width=True)
            
            
            st.markdown("---")
            st.subheader("Deep Dive Analysis")
            st.write("Select a specific run to view its detailed trade logs and interactive historical chart.")
            
            run_to_view = st.selectbox("Select Run:", selected_runs)
            if run_to_view:
                tabA, tabB = st.tabs(["📝 Trade Ledger", "📈 Interactive Chart"])
                
                with tabA:
                    trades_path = os.path.join(results_dir, f"{run_to_view}_trades.csv")
                    if os.path.exists(trades_path):
                        trades_df = pd.read_csv(trades_path)
                        if not trades_df.empty:
                            st.write(f"Displaying **{len(trades_df)}** recorded trades.")
                            
                            # Optional conditional formatting for PnL
                            def highlight_pnl(val):
                                try:
                                    color = 'rgba(0, 255, 0, 0.1)' if float(val) > 0 else 'rgba(255, 0, 0, 0.1)'
                                    return f'background-color: {color}'
                                except:
                                    return ''
                            
                            # Display styled dataframe
                            if 'PnL' in trades_df.columns:
                                st.dataframe(trades_df.style.map(highlight_pnl, subset=['PnL']), use_container_width=True)
                            else:
                                st.dataframe(trades_df, use_container_width=True)
                        else:
                            st.info("No trades were executed during this backtest run.")
                    else:
                        st.warning(f"No trade ledger found for {run_to_view}. (Was it run before this update?)")
                        
                with tabB:
                    plot_path = os.path.join(results_dir, f"{run_to_view}_plot.html")
                    if os.path.exists(plot_path):
                        with open(plot_path, "r", encoding='utf-8') as f:
                            html_content = f.read()
                            components.html(html_content, height=700, scrolling=True)
                    else:
                        st.warning(f"No interactive chart found for {run_to_view}.")

# --- TAB 5: Bulk Testing ---
with tab5:
    st.header("Bulk Testing Engine")
    st.write("Automatically slice your dataset into individual periods (e.g., Daily) and run your strategy on each slice independently to rank performance.")
    
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        data_dir = "data"
        data_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')] if os.path.exists(data_dir) else []
        
        st.info("💡 **Note:** When selecting multiple datasets, ensure they all share the same Native Granularity (e.g., all 5-minute tickers, or all Daily).")
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
                        st.success(f"✅ Combined Data Overlap Available: **{global_min}** to **{global_max}**")
                    else:
                        st.warning("⚠️ **Warning: No overlapping dates found between the selected datasets!**")
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
        
    split_freq = st.selectbox("Split Dataset By:", ["Whole Dataset (No Split)", "Daily", "Weekly", "Monthly", "Intraday (Time Windows)"], help="Choose 'Whole Dataset' to test across the entire filtered date range without breaking it down. Select 'Intraday' to test specific hours within each day.")
    
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
            
    st.markdown("**(Uses the Advanced Parameters currently set in Tab 3 `Run Backtest`)**")
    
    if st.button("▶ Run Bulk Test", type="primary", use_container_width=True):
        if not selected_bulk_data or not selected_bulk_strat:
            st.error("Please select at least one dataset and a strategy.")
        else:
            with st.spinner(f"Running Bulk {split_freq} tests across {len(selected_bulk_data)} datasets..."):
                try:
                    all_stats = []
                    
                    # 1. Load Strategy
                    strat_class = load_strategy(os.path.join(strategies_dir, selected_bulk_strat))
                    if not strat_class:
                        st.error("No valid Strategy class found in the file.")
                        st.stop()
                        
                    # 2. Iterate over all selected datasets
                    for ds_idx, dataset_file in enumerate(selected_bulk_data):
                        st.write(f"**Processing Dataset {ds_idx+1}/{len(selected_bulk_data)}: `{dataset_file}`**")
                        
                        df = pd.read_csv(os.path.join(data_dir, dataset_file))
                        df.columns = df.columns.str.strip()
                        col_map = {c.lower(): c.capitalize() for c in df.columns}
                        df.rename(columns=col_map, inplace=True)
                        if 'Volume' not in df.columns and 'volume' in col_map: 
                            df.rename(columns={'volume': 'Volume'}, inplace=True)
                        
                        dt_col = None
                        for col in df.columns:
                            if col.lower() in ['date', 'time', 'datetime', 'timestamp']:
                                dt_col = col
                                break
                                
                        if not dt_col:
                            st.warning(f"Skipping `{dataset_file}`: No datetime column found.")
                            continue
                            
                        df[dt_col] = pd.to_datetime(df[dt_col], format='mixed')
                        df.set_index(dt_col, inplace=True)
                        df.sort_index(inplace=True)
                        
                        # --- Granularity Validation ---
                        # Calculate the median time difference between rows to guess the dataset's native timeframe
                        if len(df) > 1:
                            median_diff = df.index.to_series().diff().median()
                            
                            if split_freq == "Intraday (Time Windows)" and median_diff >= pd.Timedelta(days=1):
                                st.error(f"⚠️ Granularity Mismatch for `{dataset_file}`: You requested an **Intraday** split, but this dataset appears to only contain **Daily** (or higher) candles! Skipping this file.")
                                continue
                                
                            if split_freq == "Daily" and median_diff >= pd.Timedelta(days=7):
                                st.error(f"⚠️ Granularity Mismatch for `{dataset_file}`: You requested a **Daily** split, but this dataset appears to only contain **Weekly/Monthly** candles! Skipping this file.")
                                continue
                        
                        # Apply DateTime Slicing
                        if start_datetime_bulk and end_datetime_bulk:
                            try:
                                start_dt_pd = pd.to_datetime(start_datetime_bulk)
                                end_dt_pd = pd.to_datetime(end_datetime_bulk)
                                mask = (df.index >= start_dt_pd) & (df.index <= end_dt_pd)
                                df = df.loc[mask]
                                if df.empty:
                                    st.warning(f"DateTime slice resulted in an empty dataset for {dataset_file}.")
                                    continue
                            except Exception as e:
                                st.warning(f"Error applying datetime slice: {e}. Running on full dataset.")
                        
                        
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
                                        st.warning(f"Failed to slice window {s_str}-{e_str} on {date}: {e}")
                        
                        if not chunks:
                            st.warning(f"No valid data chunks found to process in `{dataset_file}`.")
                            continue
                            
                        st.info(f"Generated {len(chunks)} {split_freq} slices for `{dataset_file}`. Executing engine...")
                        
                        # 4. Execute Loop for this dataset
                        progress_bar = st.progress(0)
                        total_chunks = len(chunks)
                        
                        for i, (chunk_label, chunk_df) in enumerate(chunks):
                            if len(chunk_df) < 5:  # Skip tiny chunks (e.g. half days with no data)
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
                            
                            # Clean up stats series for row-insertion
                            stats = stats.drop(['_strategy', '_equity_curve', '_trades'])
                            stats.name = chunk_label
                            all_stats.append(stats)
                            
                            # Update progress
                            progress_bar.progress((i + 1) / total_chunks)
                        
                    # 5. Aggregate and Display
                    if all_stats:
                        # Combine all series into a dataframe where rows are periods
                        results_df = pd.DataFrame(all_stats)
                        
                        st.success("Bulk Testing Complete!")
                        
                        # --- Auto Export Results ---
                        bulk_results_dir = "bulk_results"
                        if not os.path.exists(bulk_results_dir):
                            os.makedirs(bulk_results_dir)
                            
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                        # Use multiple dataset tagging if more than one selected
                        if len(selected_bulk_data) > 1:
                            target_tag = "Multiple_Datasets"
                        else:
                            target_tag = selected_bulk_data[0].replace('.csv', '')
                            
                        bulk_report_name = f"BULK_{split_freq}_{selected_bulk_strat.replace('.py', '')}_{target_tag}_{timestamp}.csv"
                        bulk_path = os.path.join(bulk_results_dir, bulk_report_name)
                        
                        results_df.to_csv(bulk_path)
                        st.info(f"💾 Rendered Bulk Matrix successfully exported to `{bulk_path}`!")
                        
                        if "Return [%]" in results_df.columns:
                            import plotly.express as px
                            st.markdown("---")
                            st.subheader("Return Distribution")
                            fig = px.histogram(
                                results_df, 
                                x="Return [%]", 
                                nbins=50, 
                                title="Distribution of Strategy Returns", 
                                marginal="box", 
                                color_discrete_sequence=['#00CC96']
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        st.markdown("---")
                        st.subheader("Ranked Performance Matrix")
                        
                        # Let user sort the dataframe easily
                        sort_col = st.selectbox("Sort By:", results_df.columns, index=results_df.columns.get_loc("Return [%]") if "Return [%]" in results_df.columns else 0)
                        results_df = results_df.sort_values(by=sort_col, ascending=False)
                        
                        # Optional: Highlight positive returns
                        def highlight_positive(val):
                            try:
                                color = 'rgba(0, 255, 0, 0.1)' if float(val) > 0 else 'rgba(255, 0, 0, 0.1)'
                                return f'background-color: {color}'
                            except:
                                return ''
                                
                        if "Return [%]" in results_df.columns:
                            st.dataframe(results_df.style.map(highlight_positive, subset=["Return [%]"]), use_container_width=True)
                        else:
                            st.dataframe(results_df, use_container_width=True)
                    else:
                        st.warning("All data slices were too small or failed to execute.")
                        
                except Exception as e:
                    st.error(f"Error during bulk testing: {e}")

# --- TAB 6: Optimize Parameters ---
with tab6:
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
                
                if st.button("🚀 Run Optimization", type="primary", use_container_width=True):
                    if not opt_ranges:
                        st.error("You must define valid ranges before optimizing.")
                    else:
                        st.info("💡 Note: To forcefully stop a long optimization, use the 🛑 Stop Local Server button in the sidebar.")
                        with st.spinner(f"Running {opt_method}... this may take a moment depending on range sizes!"):
                            try:
                                # 1. Prepare Data
                                df = pd.read_csv(os.path.join(data_dir, selected_opt_data))
                                df.columns = df.columns.str.strip()
                                col_map = {c.lower(): c.capitalize() for c in df.columns}
                                df.rename(columns=col_map, inplace=True)
                                if 'Volume' not in df.columns and 'volume' in col_map: 
                                    df.rename(columns={'volume': 'Volume'}, inplace=True)
                                
                                dt_col = next((c for c in df.columns if c.lower() in ['date', 'time', 'datetime', 'timestamp']), None)
                                df[dt_col] = pd.to_datetime(df[dt_col], format='mixed')
                                df.set_index(dt_col, inplace=True)
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
                                    st.info(f"💾 Rendered Metrics explicitly saved back to `{opt_dir}/` directory.")
                                except Exception as save_err:
                                    st.warning(f"Could not save output data to CSVs: {save_err}")
                                
                                # Save Plot natively
                                plot_file = os.path.join(opt_dir, f"{report_name}_plot.html")
                                bt.plot(filename=plot_file, open_browser=False, resample=False)
                                
                                # Save Heatmaps natively
                                heatmap_file = os.path.join(opt_dir, f"{report_name}_heatmap.html")
                                try:
                                    plot_heatmaps(heatmap, agg='max', filename=heatmap_file, open_browser=False)
                                except Exception as heatmap_err:
                                    st.warning(f"Could not generate interactive heatmap: {heatmap_err}")
                                
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
with tab7:
    st.header("⏱️ Paper Trading Engine (Background Daemon)")
    st.write("Run your strategy on live-updating data natively in the background. You can navigate away from this tab while engines run.")
    
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    state_files = [f for f in os.listdir(results_dir) if f.startswith('pt_state_') and f.endswith('.json')]
    
    # 1. Start New Engine Form
    with st.expander("🚀 Launch New Paper Trading Engine", expanded=len(state_files) == 0):
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
    
        if st.button("▶ Start Engine", type="primary"):
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
    st.subheader("🖥️ Active Engines Dashboard")
    
    col_ref, col_spacer = st.columns([1, 5])
    if col_ref.button("🔄 Refresh Dashboard"):
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
                
            status_color = "🟢" if state.get("status") in ["Running", "Starting"] else "🔴"
            if state.get("status") == "Error":
                status_color = "⚠️"
                
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
                    with st.expander("📈 Live Interactive Chart"):
                        try:
                            with open(plot_file, "r", encoding='utf-8') as f:
                                html_content = f.read()
                                components.html(html_content, height=650, scrolling=True)
                        except Exception as e:
                            st.warning(f"Could not load chart: {e}")
                            
                c_stop, c_del = st.columns([2, 8])
                if c_stop.button(f"🛑 Stop `{sym}` Engine", key=f"stop_{sym}"):
                    stop_path = os.path.join(results_dir, f"pt_stop_{sym}.txt")
                    with open(stop_path, 'w') as f:
                        f.write("STOP")
                    st.success(f"Signal sent to gracefully stop {sym}. It will shutdown on its next loop.")
                    time.sleep(1)
                    st.rerun()
                
                # Option to clear disconnected/stopped engines from dashboard
                if state.get("status") in ["Stopped", "Error"]:
                    if c_del.button(f"🗑️ Clean up `{sym}` Dashboard", key=f"del_{sym}"):
                        os.remove(state_path)
                        st.rerun()

# --- TAB 8: Monte Carlo Analysis ---
with tab8:
    st.header("🎲 Monte Carlo Risk Analysis")
    st.write("Stress-test your strategy by shuffling trade sequences to simulate thousands of 'what-if' market scenarios.")
    
    results_dir = "results"
    trade_files = []
    if os.path.exists(results_dir):
        trade_files = [f for f in os.listdir(results_dir) if f.endswith('_trades.csv')]
        
    if not trade_files:
        st.info("No trade ledgers found. Run a backtest in Tab 3 first to generate data.")
    else:
        mc_col1, mc_col2 = st.columns([1, 1])
        
        with mc_col1:
            selected_mc_file = st.selectbox("Select Trade Ledger:", trade_files)
            n_simulations = st.slider("Number of Simulations", min_value=100, max_value=10000, value=1000, step=100)
            
        with mc_col2:
            start_capital = st.number_input("Simulation Start Capital ($)", min_value=100, value=10000, step=1000)
            confidence_level = st.slider("Confidence Level (%)", min_value=80, max_value=99, value=95)

        if st.button("🎲 Run Monte Carlo Simulation", type="primary", use_container_width=True):
            try:
                # 1. Load Trades
                trades_df = pd.read_csv(os.path.join(results_dir, selected_mc_file))
                
                # We use ReturnPct (percentage) for shuffling as it's independent of absolute capital
                if 'ReturnPct' not in trades_df.columns:
                    st.error("The selected ledger does not contain 'ReturnPct' data. Please run a new backtest.")
                    st.stop()
                
                # Convert percentage to decimal (e.g. 2.5 -> 0.025)
                returns = trades_df['ReturnPct'].values / 100.0
                
                if len(returns) < 5:
                    st.warning("Too few trades to run a meaningful simulation. Need at least 5 trades.")
                    st.stop()

                # 2. Run Simulations
                with st.spinner(f"Simulating {n_simulations} sequences..."):
                    all_eq_curves = []
                    max_dds = []
                    final_vals = []
                    
                    for _ in range(n_simulations):
                        # Shuffle with replacement (Bootstrapping)
                        shuffled_rets = np.random.choice(returns, size=len(returns), replace=True)
                        
                        # Calculate compounding equity
                        # Equity_n = Start * Product(1 + r_i)
                        eq_curve = start_capital * np.cumprod(1 + shuffled_rets)
                        eq_curve = np.insert(eq_curve, 0, start_capital)
                        
                        all_eq_curves.append(eq_curve)
                        
                        # Max Drawdown calculation
                        peak = np.maximum.accumulate(eq_curve)
                        dd = (eq_curve - peak) / peak
                        max_dds.append(np.min(dd) * 100) # Store as %
                        
                        final_vals.append(eq_curve[-1])

                # 3. Analyze Results
                st.divider()
                st.subheader("🏁 Comparative Verdict")
                
                # Try to load the original stats for comparison
                original_dd = None
                stats_file_name = selected_mc_file.replace('_trades.csv', '_stats.csv')
                stats_path = os.path.join(results_dir, stats_file_name)
                
                if os.path.exists(stats_path):
                    try:
                        orig_stats = pd.read_csv(stats_path, index_col=0)
                        # The column name is usually '0' or matching the run name
                        original_dd = float(orig_stats.loc['Max. Drawdown [%]'].iloc[0])
                    except:
                        pass
                
                avg_final = np.mean(final_vals)
                median_dd = np.median(max_dds)
                var_dd = np.percentile(max_dds, 100 - confidence_level) # 95% Var
                
                v_col1, v_col2 = st.columns([2, 1])
                
                with v_col1:
                    if original_dd is not None:
                        diff = median_dd - original_dd
                        if diff < -5: # Median is much worse (more negative)
                            st.warning(f"### Verdict: **Sequence Luck Detected** ⚠️")
                            st.write(f"Your original backtest (DD: **{original_dd:.2f}%**) was significantly luckier than the average simulation (Median DD: **{median_dd:.2f}%**). The order of trades in your backtest was ideal and likely won't repeat. Expect deeper drawdowns in live trading.")
                        elif diff > 5: # Median is much better
                            st.success(f"### Verdict: **Pessimistic Backtest** 🛡️")
                            st.write(f"Your original backtest (DD: **{original_dd:.2f}%**) was actually 'unlucky'. Most simulations (Median DD: **{median_dd:.2f}%**) show a smoother path. Your strategy is likely more robust than your single test suggests.")
                        else:
                            st.info(f"### Verdict: **Statistically Robust** ✅")
                            st.write(f"Your original backtest (DD: **{original_dd:.2f}%**) is very close to the simulated median (DD: **{median_dd:.2f}%**). This suggests your results are not dependent on trade sequence and are highly reliable.")
                    else:
                        st.info("Original stats file not found for comparison. Running independent analysis.")

                with v_col2:
                    st.write("**Key Comparison**")
                    if original_dd is not None:
                        st.metric("Original Max DD", f"{original_dd:.2f}%")
                    st.metric("Median Simulated DD", f"{median_dd:.2f}%", delta=f"{median_dd - (original_dd if original_dd else 0):.2f}%", delta_color="inverse")
                
                st.divider()
                st.subheader("Detailed Metrics")
                m1, m2, m3 = st.columns(3)
                m1.metric("Expected Final Equity", f"${avg_final:,.2f}")
                m2.metric("Median Max Drawdown", f"{median_dd:.2f}%")
                m3.metric(f"{confidence_level}% Probable Max DD (VaR)", f"{var_dd:.2f}%")

                # 4. Visualization
                st.divider()
                viz_col1, viz_col2 = st.columns([3, 2])
                
                with viz_col1:
                    st.write("### Equity Curve 'Spaghetti' Plot")
                    st.caption(f"Showing 50 random samples out of {n_simulations} simulations.")
                    
                    # Prepare data for plotting
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
                                 height=450,
                                 sizing_mode="stretch_width")
                    
                    # --- Dark Mode Styling ---
                    p_mc.background_fill_color = "#0e1117"
                    p_mc.border_fill_color = "#0e1117"
                    p_mc.title.text_color = "white"
                    p_mc.xaxis.axis_label_text_color = "white"
                    p_mc.yaxis.axis_label_text_color = "white"
                    p_mc.xaxis.major_label_text_color = "white"
                    p_mc.yaxis.major_label_text_color = "white"
                    p_mc.grid.grid_line_color = "#333333"
                    # -------------------------

                    # Add each sample path
                    for idx in sample_indices:
                        curve = all_eq_curves[idx]
                        p_mc.line(list(range(len(curve))), curve, line_width=1, alpha=0.3, color="gray")
                    
                    # Highlight the average path in a different color
                    avg_curve = np.mean(all_eq_curves, axis=0)
                    p_mc.line(list(range(len(avg_curve))), avg_curve, line_width=4, color="#00d4ff", legend_label="Average Path")
                    
                    p_mc.yaxis.formatter = NumeralTickFormatter(format="$0,0")
                    p_mc.legend.location = "top_left"
                    p_mc.legend.click_policy = "hide"
                    p_mc.legend.background_fill_color = "#0e1117"
                    p_mc.legend.label_text_color = "white"
                    p_mc.legend.background_fill_alpha = 0.8
                    
                    # Convert Bokeh figure to HTML string and render
                    mc_html = file_html(p_mc, CDN, "Monte Carlo Spaghetti Plot")
                    components.html(mc_html, height=480)
                    
                with viz_col2:
                    st.write("### Max Drawdown Distribution")
                    st.caption("Distribution of worst-case drawdowns across all simulations.")
                    
                    # Create a clean histogram
                    counts, bin_edges = np.histogram(max_dds, bins=25)
                    # Round bin edges for cleaner X-axis labels
                    bin_labels = [f"{x:.1f}%" for x in bin_edges[:-1]]
                    
                    hist_df = pd.DataFrame({
                        'Drawdown Probability': counts
                    }, index=bin_labels)
                    
                    st.bar_chart(hist_df, use_container_width=True)

                st.info("💡 **Insight:** If your 'Original Backtest' Max Drawdown was much lower than the 'Median Max Drawdown' shown here, your backtest was likely 'lucky' with the order of trades. Plan your risk based on the Monte Carlo results instead.")

            except Exception as e:
                st.error(f"Monte Carlo simulation failed: {e}")
