import dash
from dash import dcc, html, Input, Output, State, dash_table,callback_context
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
import re
import math
import requests
import io
from pathlib import Path

# Configuration
#FLASK_APP_URL = "http://127.0.0.1:5000"

FLASK_APP_URL = "https://crude-backend-idletank.onrender.com"

PRIMARY_FOLDER = r"G:\tmp"
FALLBACK_FOLDER = str(Path.home() / "Downloads")

# State colors
STATE_COLORS = {
    'READY': '#10b981',
    'FEEDING': '#3b82f6',
    'EMPTY': '#ef4444',
    'FILLING': '#f59e0b',
    'FILLED': '#8b5cf6',
    'SETTLING': '#eab308',
    'LAB': '#06b6d4',
    'SUSPENDED': '#6b7280',
    'IDLE': '#0d47a1',
    'MAINTENANCE': '#ec4899',
    'CLEANING': '#14b8a6',
    'RESERVED': '#a855f7',
    'N/A - NO MATCH': '#94a3b8'
}

# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server
app.title = "Tank Simulation Dashboard"

# Helper functions
def get_data_folder():
    if os.path.exists(PRIMARY_FOLDER) and os.path.isdir(PRIMARY_FOLDER):
        csv_files = [f for f in os.listdir(PRIMARY_FOLDER) if f.endswith('.csv')]
        if csv_files:
            return PRIMARY_FOLDER
    
    if os.path.exists(FALLBACK_FOLDER) and os.path.isdir(FALLBACK_FOLDER):
        return FALLBACK_FOLDER
    
    return PRIMARY_FOLDER

def safe_read_csv(filepath, **kwargs):
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            return pd.read_csv(filepath, encoding=encoding, on_bad_lines='skip', **kwargs)
        except Exception:
            continue
    try:
        return pd.read_csv(filepath, on_bad_lines='skip', **kwargs)
    except Exception as e:
        print(f"Failed to read {os.path.basename(filepath)}: {e}")
        return None

def load_data():
    folder_path = get_data_folder()
    dataframes = {}
    crude_mix = {}
    processing_rate_html = None
    use_flask = False
    
    file_patterns = {
        'log_df': 'simulation_log*.csv',
        'summary_df': 'daily_summary*.csv',
        'cargo_df': 'cargo_report*.csv',
        'snapshot_df': 'tank_snapshots*.csv'
    }
    
    # 1. Determine Source
    if os.path.exists(folder_path):
        has_files = any(len([f for f in os.listdir(folder_path) if p.replace('*','') in f]) > 0 for p in file_patterns.values())
        if not has_files:
            use_flask = True
    else:
        use_flask = True
    
    # 2. Download/Load Logic
    if use_flask:
        print("🌍 Downloading from Backend...")
        endpoints = {
            'summary_df': f"{FLASK_APP_URL}/download/daily_summary.csv", 
            'log_df': f"{FLASK_APP_URL}/download/simulation_log.csv",
            'cargo_df': f"{FLASK_APP_URL}/download/cargo_report.csv",
            'snapshot_df': f"{FLASK_APP_URL}/download/tank_snapshots.csv"
        }
        
        for df_name, url in endpoints.items():
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    csv_data = response.content.decode('utf-8')
                    dataframes[df_name] = pd.read_csv(io.StringIO(csv_data))
                    print(f"   ✅ {df_name}: {len(dataframes[df_name])} rows loaded.")
                else:
                    dataframes[df_name] = None
            except Exception as e:
                print(f"   ❌ Error {df_name}: {e}")
                dataframes[df_name] = None
    else:
        # Local Load: Force pick the largest file to avoid partial logs
        for df_name, pattern in file_patterns.items():
            matching_files = [f for f in os.listdir(folder_path) if f.endswith('.csv') and pattern.replace('*', '') in f]
            if matching_files:
                # Sort by size (largest first) to ensure we get the full simulation
                matching_files.sort(key=lambda x: os.path.getsize(os.path.join(folder_path, x)), reverse=True)
                latest_file = matching_files[0]
                dataframes[df_name] = safe_read_csv(os.path.join(folder_path, latest_file))
            else:
                dataframes[df_name] = None

    # 3. Assign Dataframes
    log_df = dataframes.get('log_df')
    summary_df = dataframes.get('summary_df')
    cargo_df = dataframes.get('cargo_df')
    snapshot_df = dataframes.get('snapshot_df')
    
    # --- FIX: Ensure Daily Summary has a 'Date' column ---
    if summary_df is not None:
        # If 'Date' is missing, check if it's the first unnamed column (index)
        if 'Date' not in summary_df.columns:
            first_col = summary_df.columns[0]
            if 'Unnamed' in str(first_col) or first_col == '':
                summary_df.rename(columns={first_col: 'Date'}, inplace=True)
            # If it was set as index
            elif summary_df.index.name == 'Date':
                summary_df.reset_index(inplace=True)

    # 4. Get Crude Mix
    if use_flask:
        try:
            resp = requests.get(f"{FLASK_APP_URL}/api/get_crude_mix", timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("crude_mix_data", []):
                    crude_mix[item.get("name")] = float(item.get("percentage", 0))
        except: pass
    elif log_df is not None and not log_df.empty:
        ready_events = log_df[log_df['Event'] == 'READY_2']
        if not ready_events.empty:
            for idx, row in ready_events.iterrows():
                message = str(row.get('Message', ''))
                mix_match = re.search(r'Mix:\s*\[(.*?)\]', message, re.IGNORECASE)
                if mix_match:
                    mix_str = mix_match.group(1)
                    for item in mix_str.split(','):
                        item = item.strip()
                        crude_pct = re.match(r'([^:]+):\s*([\d.]+)%', item)
                        if crude_pct:
                             crude_mix[crude_pct.group(1).strip()] = float(crude_pct.group(2))

    # 5. Pre-process Log (ENSURE NO TAIL/LIMIT HERE)
    if log_df is not None:
        try:
            log_df['Timestamp'] = pd.to_datetime(log_df['Timestamp'], format='%d/%m/%Y %H:%M', dayfirst=True)
        except:
            log_df['Timestamp'] = pd.to_datetime(log_df['Timestamp'], errors='coerce')
        
        if 'Timestamp' in log_df.columns:
            # Sort Oldest to Newest
            log_df = log_df.sort_values('Timestamp', ascending=True).reset_index(drop=True)

        sim_start = log_df[log_df['Event'] == 'SIM_START']
        if not sim_start.empty:
            rate_match = re.search(r'processing rate:\s*([\d,]+)', str(sim_start.iloc[0].get('Message', '')))
            if rate_match:
                processing_rate_html = float(rate_match.group(1).replace(',', ''))

    if snapshot_df is not None:
        try:
            snapshot_df['_Timestamp'] = pd.to_datetime(snapshot_df.iloc[:, 0], format='%d/%m/%Y %H:%M', dayfirst=True, errors='coerce')
        except: pass

    return log_df, summary_df, cargo_df, snapshot_df, crude_mix, processing_rate_html

def get_all_tank_ids(log_df, snapshot_df):
    detected_tanks = set()
    
    if snapshot_df is not None:
        tank_cols = [col for col in snapshot_df.columns if re.match(r'^Tank\d+$', col)]
        for col in tank_cols:
            try:
                detected_tanks.add(int(col[4:]))
            except ValueError:
                continue
                
        state_cols = [col for col in snapshot_df.columns if re.match(r'^State\d+$', col)]
        for col in state_cols:
            try:
                detected_tanks.add(int(col[5:]))
            except ValueError:
                continue
    
    return sorted(list(detected_tanks))

# ----------------- STREAMLIT LOGIC REPLICATED START -----------------
def get_tank_status(log_df, snapshot_df, timestamp, all_tank_ids):
    tank_status = {}
    
    # Method 1: Try to get status from log_df (Lower Priority)
    if log_df is not None and not log_df.empty:
        filtered = log_df[log_df['Timestamp'] <= timestamp].copy()
        if not filtered.empty:
            latest_row = filtered.iloc[-1]
            for tank_id in all_tank_ids:
                col_name = f'Tank{tank_id}'
                if col_name in latest_row.index:
                    status = latest_row[col_name]
                    if pd.notna(status) and isinstance(status, str):
                        tank_status[tank_id] = status.strip().upper()

    # Method 2: Read from HORIZONTAL snapshot format (Highest Priority - Strict Historical)
    if snapshot_df is not None and not snapshot_df.empty and '_Timestamp' in snapshot_df.columns:
        
        # STREAMLIT LOGIC: Use the most recent snapshot AT or BEFORE the selected time.
        matched_rows = snapshot_df[snapshot_df['_Timestamp'] <= timestamp]
        
        if matched_rows.empty:
            # If no snapshot before this time, use the first one 
            latest_snapshot = snapshot_df.iloc[0] 
        else:
            # Use the most recent snapshot before or at this time
            latest_snapshot = matched_rows.iloc[-1]
        
        for tank_id in all_tank_ids:
            status_col_name = f'State{tank_id}'
            
            # FIX applied to Streamlit logic: Ensure snapshot state (Method 2) ALWAYS overwrites 
            # log state (Method 1) to correctly show FILLING/EMPTY status.
            if status_col_name in latest_snapshot.index: 
                value = latest_snapshot[status_col_name]
                if pd.notna(value) and str(value).strip():
                    tank_status[tank_id] = str(value).strip().upper()
    
    # Fill in any tanks that are still missing
    for tank_id in all_tank_ids:
        if tank_id not in tank_status:
            tank_status[tank_id] = 'READY'
    
    return tank_status

def get_tank_volume(snapshot_df, timestamp, tank_id):
    if snapshot_df is None or snapshot_df.empty or '_Timestamp' not in snapshot_df.columns:
        return 0
    
    # Convert timestamp to pandas Timestamp for comparison
    if isinstance(timestamp, str):
        timestamp = pd.to_datetime(timestamp)
    
    # STREAMLIT LOGIC: Use the most recent snapshot AT or BEFORE the selected time.
    snapshot_df_sorted = snapshot_df.sort_values('_Timestamp')
    matched_rows = snapshot_df_sorted[snapshot_df_sorted['_Timestamp'] <= timestamp]
    
    if matched_rows.empty:
        # If no snapshot before this time, use the first one
        latest_snapshot = snapshot_df_sorted.iloc[0]
    else:
        # Use the most recent snapshot before or at this time
        latest_snapshot = matched_rows.iloc[-1]
    
    tank_col_name = f'Tank{tank_id}'
    
    if tank_col_name in latest_snapshot.index:
        value = latest_snapshot[tank_col_name]
        
        if pd.isna(value):
            return 0
        
        vol_str = str(value).replace(',', '').replace(' ', '').strip()
        
        try:
            volume = float(vol_str)
            return max(0, volume)
        except ValueError:
            return 0
    
    return 0
# ----------------- STREAMLIT LOGIC REPLICATED END -----------------

# Load data globally
log_df, summary_df, cargo_df, snapshot_df, crude_mix, processing_rate = load_data()
all_tank_ids = get_all_tank_ids(log_df, snapshot_df)

# Get time range
if log_df is not None and not log_df.empty:
    min_time = log_df['Timestamp'].min()
    max_time = log_df['Timestamp'].max()
elif snapshot_df is not None and '_Timestamp' in snapshot_df.columns:
    min_time = snapshot_df['_Timestamp'].min()
    max_time = snapshot_df['_Timestamp'].max()
else:
    min_time = datetime.now()
    max_time = datetime.now() + timedelta(days=1)

# Layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("🛢️ Crude Oil Tank Simulation Dashboard", style={'color': 'white', 'margin': '0'}),
        html.H3("Dynamic Multi-Tank System Monitor", style={'color': '#cccccc', 'margin': '10px 0 0 0'}),
    ], style={'backgroundColor': '#1f2937', 'padding': '20px', 'marginBottom': '20px'}),
    
    # Main content
    html.Div([
        # Debug info
        html.Div(id='debug-info', style={'backgroundColor': '#fffacd', 'padding': '10px', 'marginBottom': '10px', 'borderRadius': '5px'}),
        
        # Time selector
        html.Div([
            html.H3("⏰ Select Time Point", style={'marginBottom': '15px'}),
            html.Div([
                html.Div([
                    html.Label("📅 Select Date"),
                    dcc.Dropdown(
                        id='date-selector',
                        options=[{'label': d.strftime('%d/%m/%Y'), 'value': d.strftime('%Y-%m-%d')} 
                                for d in pd.date_range(min_time.date(), max_time.date(), freq='D')],
                        value=min_time.strftime('%Y-%m-%d'),
                        clearable=False
                    ),
                ], style={'width': '38%', 'display': 'inline-block', 'marginRight': '2%'}),
                
                html.Div([
                    html.Label("🕐 Select Time (HH:MM)"),
                    dcc.Input(
                        id='time-input',
                        type='text',
                        value='00:00',
                        placeholder='HH:MM',
                        style={'width': '100%', 'padding': '8px'}
                    ),
                ], style={'width': '38%', 'display': 'inline-block', 'marginRight': '2%'}),
                
                html.Div([
                    html.Button('🔄 Refresh', id='refresh-btn', n_clicks=0,
                               style={'width': '100%', 'padding': '8px', 'marginTop': '20px', 
                                      'backgroundColor': '#4CAF50', 'color': 'white', 'border': 'none',
                                      'borderRadius': '5px', 'cursor': 'pointer'})
                ], style={'width': '18%', 'display': 'inline-block'}),
            ]),
        ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'marginBottom': '20px'}),
        
        # Metrics row
        html.Div(id='metrics-row', style={'marginBottom': '20px'}),
        
        # Certified stock
        html.Div(id='certified-stock-metrics', style={'marginBottom': '20px'}),
        
        # Tank grid
        html.Div(id='tank-grid', style={'marginBottom': '20px'}),
        
        # Tabs
        dcc.Tabs(id='tabs', value='crude-mix', children=[
            dcc.Tab(label='🛢️ Crude Mix', value='crude-mix'),
            dcc.Tab(label='📋 Events Log', value='events'),
            dcc.Tab(label='📊 Certified Stock', value='stock'),
            dcc.Tab(label='🚢 Cargo Report', value='cargo'),
            dcc.Tab(label='📈 Daily Summary', value='summary'),
        ]),
        html.Div(id='tab-content', style={'marginTop': '20px'}),
        
    ], style={'padding': '20px', 'maxWidth': '1400px', 'margin': '0 auto'}),
    
    # Store for selected timestamp
    dcc.Store(id='selected-timestamp'),
])

def show_debug_info(date_str, time_str, n_clicks):
    debug_lines = []
    debug_lines.append(f"📅 Selected Date: {date_str}")
    debug_lines.append(f"🕐 Selected Time: {time_str}")
    debug_lines.append(f"🔄 Refresh clicks: {n_clicks}")
    debug_lines.append(f"📊 Log DF: {'Loaded' if log_df is not None else 'None'} ({len(log_df) if log_df is not None else 0} rows)")
    debug_lines.append(f"📊 Snapshot DF: {'Loaded' if snapshot_df is not None else 'None'} ({len(snapshot_df) if snapshot_df is not None else 0} rows)")
    
    if snapshot_df is not None and '_Timestamp' in snapshot_df.columns:
        debug_lines.append(f"✅ Snapshot has _Timestamp column")
        debug_lines.append(f"📅 Snapshot time range: {snapshot_df['_Timestamp'].min()} to {snapshot_df['_Timestamp'].max()}")
    else:
        debug_lines.append(f"❌ Snapshot missing _Timestamp column")
    
    return html.Div([html.P(line, style={'margin': '2px'}) for line in debug_lines])

@app.callback(
    [Output('selected-timestamp', 'data'),
     Output('date-selector', 'options'),
     Output('date-selector', 'value')],
    [Input('date-selector', 'value'),
     Input('time-input', 'value'),
     Input('refresh-btn', 'n_clicks')],
    [State('date-selector', 'options')]
)
def update_timestamp(date_str, time_str, n_clicks, current_options):
    # Global variables need to be updated
    global log_df, summary_df, cargo_df, snapshot_df, crude_mix, processing_rate, all_tank_ids, min_time, max_time
    
    ctx = callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    
    # 1. RELOAD DATA Logic
    if trigger_id == 'refresh-btn' or len(all_tank_ids) == 0:
        print("🔄 Refreshing: Checking Backend for data...")
        new_log, new_sum, new_cargo, new_snap, new_mix, new_rate = load_data()
        
        if new_log is not None or new_snap is not None:
            # Update globals
            log_df, summary_df, cargo_df, snapshot_df = new_log, new_sum, new_cargo, new_snap
            crude_mix, processing_rate = new_mix, new_rate
            all_tank_ids = get_all_tank_ids(log_df, snapshot_df)
            
            # Recalculate Time Range from the new data
            if log_df is not None and not log_df.empty:
                min_time = log_df['Timestamp'].min()
                max_time = log_df['Timestamp'].max()
                # FORCE JUMP TO START DATE
                date_str = min_time.strftime('%Y-%m-%d')
                print(f"✅ Data loaded. Simulation Start: {date_str}")
            elif snapshot_df is not None:
                min_time = snapshot_df['_Timestamp'].min()
                max_time = snapshot_df['_Timestamp'].max()
                date_str = min_time.strftime('%Y-%m-%d')
                print(f"✅ Snapshot loaded. Start: {date_str}")
        else:
            print("⚠️ Backend connection attempted, but data is empty/None.")

    # 2. UPDATE DROPDOWN OPTIONS (To match new data range)
    # Ensure min_time/max_time are valid (fallback to now if needed)
    try:
        if pd.isna(min_time): min_time = datetime.now()
        if pd.isna(max_time): max_time = datetime.now() + timedelta(days=1)
    except:
        min_time = datetime.now()
        max_time = datetime.now() + timedelta(days=1)
        
    new_options = [{'label': d.strftime('%d/%m/%Y'), 'value': d.strftime('%Y-%m-%d')} 
                   for d in pd.date_range(min_time.date(), max_time.date(), freq='D')]

    # 3. PARSE FINAL TIMESTAMP
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        time_str = str(time_str).strip()
        time_parts = time_str.replace(':', ' ').replace('-', ' ').split()
        if len(time_parts) >= 2:
            h, m = int(time_parts[0]), int(time_parts[1])
        elif len(time_parts) == 1 and time_parts[0].isdigit():
            h, m = int(time_parts[0]), 0
        else:
            h, m = 0, 0
            
        timestamp = datetime.combine(date_obj, datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time())
        
        # Return: Timestamp Data, New Options, New Value (Force Jump)
        return timestamp.isoformat(), new_options, date_str
        
    except Exception as e:
        print(f"❌ Date Error: {e}")
        return min_time.isoformat(), new_options, min_time.strftime('%Y-%m-%d')

@app.callback(
    Output('metrics-row', 'children'),
    Input('selected-timestamp', 'data')
)
def update_metrics(timestamp_str):
    if not timestamp_str:
        timestamp = min_time
    else:
        timestamp = pd.to_datetime(timestamp_str)
    
    tank_status = get_tank_status(log_df, snapshot_df, timestamp, all_tank_ids)
    
    metrics = {}
    for state in STATE_COLORS.keys():
        count = sum(1 for s in tank_status.values() if s == state)
        if count > 0:
            metrics[state] = count
    
    metric_cards = []
    for state, count in metrics.items():
        color = STATE_COLORS.get(state, '#6b7280')
        metric_cards.append(
            html.Div([
                html.H4(state, style={'margin': '0', 'color': 'white'}),
                html.H2(str(count), style={'margin': '10px 0 0 0', 'color': 'white'}),
            ], style={
                'backgroundColor': color,
                'padding': '20px',
                'borderRadius': '10px',
                'textAlign': 'center',
                'flex': '1',
                'margin': '5px'
            })
        )
    
    return html.Div(metric_cards, style={'display': 'flex', 'flexWrap': 'wrap'})

@app.callback(
    Output('certified-stock-metrics', 'children'),
    Input('selected-timestamp', 'data')
)
def update_certified_stock(timestamp_str):
    if not timestamp_str:
        timestamp = min_time
    else:
        timestamp = pd.to_datetime(timestamp_str)
    
    tank_status = get_tank_status(log_df, snapshot_df, timestamp, all_tank_ids)
    
    certified_stock = 0.0
    for tank_id in all_tank_ids:
        if tank_status.get(tank_id) in ['READY', 'FEEDING']:
            volume = get_tank_volume(snapshot_df, timestamp, tank_id)
            certified_stock += volume
    
    certified_stock_mmbl = certified_stock / 1_000_000
    
    days_remaining = certified_stock / processing_rate if processing_rate and processing_rate > 0 else 0
    ready_feeding = sum(1 for s in tank_status.values() if s in ['READY', 'FEEDING']) 
    
    return html.Div([
        html.H3("📊 Certified Stock at Selected Time"),
        html.Div([
            html.Div([
                html.H4("Certified Stock (MMbbl)"),
                html.H2(f"{certified_stock_mmbl:.3f}"),
            ], style={'flex': '1', 'padding': '20px', 'backgroundColor': '#f3f4f6', 'borderRadius': '10px', 'margin': '5px'}),
            
            html.Div([
                html.H4("Days Remaining"),
                html.H2(f"{days_remaining:.2f}" if days_remaining > 0 else "N/A"),
            ], style={'flex': '1', 'padding': '20px', 'backgroundColor': '#f3f4f6', 'borderRadius': '10px', 'margin': '5px'}),
            
            html.Div([
                html.H4("Ready + Feeding Tanks"),
                html.H2(str(ready_feeding)),
            ], style={'flex': '1', 'padding': '20px', 'backgroundColor': '#f3f4f6', 'borderRadius': '10px', 'margin': '5px'}),
        ], style={'display': 'flex'}),
    ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px'})

@app.callback(
    Output('tank-grid', 'children'),
    Input('selected-timestamp', 'data')
)
def update_tank_grid(timestamp_str):
    if not timestamp_str:
        timestamp = min_time
    else:
        timestamp = pd.to_datetime(timestamp_str)
    
    tank_status = get_tank_status(log_df, snapshot_df, timestamp, all_tank_ids)
    num_tanks = len(all_tank_ids)
    
    # --- FIX 1 APPLIED HERE: Handle 0 tanks to prevent ZeroDivisionError ---
    if num_tanks == 0:
        return html.Div([
            html.H3("⏳ Connecting to Simulation Backend..."),
            html.P("Waiting for tank data. If this persists for >1 minute, check Backend logs."),
            html.P("Note: Render Free Tier servers may take 50s to wake up.")
        ], style={'backgroundColor': '#fff3cd', 'padding': '20px', 'borderRadius': '10px', 'textAlign': 'center'})

    if num_tanks <= 4:
        cols_per_row = max(1, num_tanks) # Force at least 1 column
    elif num_tanks <= 9:
        cols_per_row = 3
    elif num_tanks <= 16:
        cols_per_row = 4
    elif num_tanks <= 25:
        cols_per_row = 5
    else:
        cols_per_row = 6
    # ---------------------------------------------------------------------
    
    num_rows = math.ceil(num_tanks / cols_per_row)
    
    grid = []
    tank_index = 0
    
    for row in range(num_rows):
        row_tanks = []
        for col in range(cols_per_row):
            if tank_index < num_tanks:
                tank_id = all_tank_ids[tank_index]
                state = tank_status.get(tank_id, 'READY')
                color = STATE_COLORS.get(state, '#6b7280')
                
                # Volume retrieval
                volume = get_tank_volume(snapshot_df, timestamp, tank_id)
                volume_display = f"{volume:,.0f} bbl"
                
                row_tanks.append(
                    html.Div([
                        html.Div(f"Tank {tank_id}", style={'fontSize': '24px', 'fontWeight': 'bold', 'marginBottom': '5px'}),
                        html.Div(state, style={'fontSize': '16px', 'margin': '5px 0', 'background': 'rgba(255,255,255,0.2)', 
                                              'padding': '3px', 'borderRadius': '5px'}),
                        html.Div(volume_display, style={'fontSize': '14px', 'fontWeight': 'bold'}),
                    ], style={
                        'backgroundColor': color,
                        'padding': '20px',
                        'borderRadius': '12px',
                        'textAlign': 'center',
                        'color': 'white',
                        'margin': '5px',
                        'flex': '1',
                        'minHeight': '120px'
                    })
                )
                tank_index += 1
        
        grid.append(html.Div(row_tanks, style={'display': 'flex', 'marginBottom': '10px'}))
    
    return html.Div([
        html.H3(f"🛢️ Tank Status Grid - {num_tanks} Tanks"),
        html.P(f"Viewing time: {timestamp.strftime('%d/%m/%Y %H:%M')}", style={'color': '#666', 'fontSize': '16px', 'fontWeight': 'bold'}),
        html.Div(grid)
    ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px'})

@app.callback(
    Output('tab-content', 'children'),
    [Input('tabs', 'value'),
     Input('selected-timestamp', 'data')]
)
def render_tab_content(active_tab, timestamp_str):
    if active_tab == 'events':
        if log_df is not None and not log_df.empty:
            display_df = log_df.copy()
            
            if 'Timestamp' in display_df.columns:
                display_df = display_df.sort_values('Timestamp', ascending=True)
                display_df['Timestamp'] = display_df['Timestamp'].dt.strftime('%d/%m/%Y %H:%M')
            
            cols = ['Timestamp', 'Level', 'Event', 'Tank', 'Message']
            display_cols = [col for col in cols if col in display_df.columns]
            
            return html.Div([
                html.H3(f"📋 Full Event Log ({len(display_df)} rows)"), 
                dash_table.DataTable(
                    data=display_df[display_cols].to_dict('records'),
                    columns=[{"name": i, "id": i} for i in display_cols],
                    page_action='native',
                    page_size=50,
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'padding': '8px', 'minWidth': '100px'},
                    style_header={'fontWeight': 'bold', 'backgroundColor': '#f3f4f6'},
                    sort_action='native',
                    filter_action='native'
                )
            ])
        return html.Div("No event log available")

    elif active_tab == 'summary':
        if summary_df is not None:
            return html.Div([
                html.H3("📈 Daily Summary"),
                dash_table.DataTable(
                    data=summary_df.to_dict('records'),
                    # This dynamically grabs columns, so 'Date' will now show up
                    columns=[{"name": i, "id": i} for i in summary_df.columns],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'padding': '10px'},
                    page_action='native',
                    page_size=15
                )
            ])
        return html.Div("No summary data available")
        
    elif active_tab == 'crude-mix':
        if crude_mix and len(crude_mix) > 0:
            mix_df = pd.DataFrame([{"Crude Name": c, "Percentage (%)": v} for c, v in crude_mix.items()])
            fig = go.Figure(data=[go.Pie(labels=list(crude_mix.keys()), values=list(crude_mix.values()), hole=0.3)])
            fig.update_layout(title='Crude Mix Distribution', height=400)
            return html.Div([
                html.H3("🛢️ Crude Mix"),
                dash_table.DataTable(data=mix_df.to_dict('records'), columns=[{"name": i, "id": i} for i in mix_df.columns]),
                dcc.Graph(figure=fig)
            ])
        return html.Div("No crude mix data available")
    
    elif active_tab == 'stock':
        if snapshot_df is not None and '_Timestamp' in snapshot_df.columns:
            # Plot 1 out of every 100 points for speed
            step = max(1, len(snapshot_df) // 100) 
            plot_df = snapshot_df.iloc[::step].copy()
            timestamps = []
            certified_stocks = []
            for _, row in plot_df.iterrows():
                c_stock = 0.0
                for tid in all_tank_ids:
                    if row.get(f'State{tid}', '').strip().upper() in ['READY', 'FEEDING']:
                        try: c_stock += float(str(row.get(f'Tank{tid}', '0')).replace(',', ''))
                        except: pass
                timestamps.append(row['_Timestamp'])
                certified_stocks.append(c_stock / 1_000_000)
            
            fig = px.line(x=timestamps, y=certified_stocks, title='Certified Stock Timeline')
            fig.update_layout(height=500)
            return html.Div([html.H3("📊 Certified Stock"), dcc.Graph(figure=fig)])
        return html.Div("No snapshot data")
    
    elif active_tab == 'cargo':
         if cargo_df is not None:
            return html.Div([html.H3("🚢 Cargo Schedule"), dash_table.DataTable(data=cargo_df.to_dict('records'), columns=[{"name": i, "id": i} for i in cargo_df.columns], style_table={'overflowX': 'auto'})])
         return html.Div("No cargo data")

    return html.Div("Select a tab")
# Run the app
if __name__ == '__main__':
    #app.run(debug=True, port=8051)
     app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8051)))