import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
import re
import math
import requests
import io

#FLASK_APP_URL = "https://crude-sim-backend.onrender.com"
FLASK_APP_URL = "http://127.0.0.1:5004"


# Try to import Excel support libraries
try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

# Page config
st.set_page_config(
    page_title="Tank Simulation Dashboard",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .tank-card {
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        margin: 5px;
        font-weight: bold;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# State colors
STATE_COLORS = {
    'READY': '#10b981',      # Green
    'FEEDING': '#3b82f6',    # Blue
    'EMPTY': '#ef4444',      # Red
    'FILLING': '#f59e0b',    # Orange
    'FILLED': '#8b5cf6',     # Purple
    'SETTLING': '#eab308',   # Yellow
    'LAB': '#06b6d4',        # Cyan
    'SUSPENDED': '#6b7280',  # Gray
    'IDLE': '#0d47a1',       # DARK BLUE
    'MAINTENANCE': '#ec4899', # Pink
    'CLEANING': '#14b8a6',   # Teal
    'RESERVED': '#a855f7'    # Purple
}

# Helper function to read CSV with multiple encoding attempts
def safe_read_csv(filepath, **kwargs):
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            return pd.read_csv(filepath, encoding=encoding, on_bad_lines='skip', **kwargs)
        except Exception:
            continue
    # Last resort - try without encoding specification
    try:
        return pd.read_csv(filepath, on_bad_lines='skip', **kwargs)
    except Exception as e:
        st.error(f"Failed to read {os.path.basename(filepath)}: {e}")
        return None


def load_data():
    """
    Load simulation data by downloading directly from the LOCAL Flask service
    and reading it into memory.
    """
    st.info(f"Connecting to Flask server at {FLASK_APP_URL}...")

    # Define the endpoints we need
    endpoints = {
      
        'summary_df': f"{FLASK_APP_URL}/download/daily_summary.csv", 
        'log_df': f"{FLASK_APP_URL}/download/simulation_log.csv",
        'cargo_df': f"{FLASK_APP_URL}/download/cargo_report.csv",
        'snapshot_df': f"{FLASK_APP_URL}/download/tank_snapshots.csv"
    }
    
    dataframes = {}
    crude_mix = {}
    processing_rate_html = None
    
    # Loop through and try to download each file
    for df_name, url in endpoints.items():
        try:
            response = requests.get(url)
            
            if response.status_code == 200:
                # Read the CSV content from the response
                csv_data = response.content.decode('utf-8')
                
                # Use io.StringIO to turn the text string into a file-like object
                # that pandas can read
                dataframes[df_name] = pd.read_csv(io.StringIO(csv_data))
                st.success(f"Successfully loaded {df_name}")
            else:
                st.warning(f"Could not load {df_name}. Server responded with {response.status_code}.")
                dataframes[df_name] = None
                
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to connect to Flask app for {df_name} at {url}. Is the Flask app running?")
            dataframes[df_name] = None
    
    # Assign to the variables your app expects
    log_df = dataframes.get('log_df')
    summary_df = dataframes.get('summary_df')
    cargo_df = dataframes.get('cargo_df')
    snapshot_df = dataframes.get('snapshot_df')
    
    # --- START FIX: Load Crude Mix from its own dedicated Flask endpoint ---
    # This completely replaces the old log-parsing logic
    try:
        mix_url = f"{FLASK_APP_URL}/api/get_crude_mix"
        response = requests.get(mix_url)
        if response.status_code == 200:
            data = response.json()
            # The data is expected as: {"crude_mix_data": [{"name": "X", "percentage": "Y"}, ...]}
            if "crude_mix_data" in data and isinstance(data["crude_mix_data"], list):
                for item in data["crude_mix_data"]:
                    crude_mix[item.get("name")] = float(item.get("percentage", 0))
                st.success(f"✅ Loaded crude mix from Flask: {len(crude_mix)} crude types")
            else:
                st.warning("Could not parse crude mix data from Flask.")
        else:
            st.warning(f"Could not load crude mix. Server responded with {response.status_code}.")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to Flask for crude mix at {mix_url}.")
    except Exception as e:
        st.error(f"Error processing crude mix data: {e}")
    # --- END FIX ---
    
    # --- (The rest of this is your original processing logic) ---
    
    if log_df is not None:
        try:
            log_df['Timestamp'] = pd.to_datetime(log_df['Timestamp'], format='%d/%m/%Y %H:%M', dayfirst=True)
        except Exception:
            try:
                log_df['Timestamp'] = pd.to_datetime(log_df['Timestamp'], format='%d/%m/%Y %H:%M', dayfirst=True, errors='coerce')
            except Exception as e:
                st.error(f"Timestamp parsing error: {e}")
        
        if 'Timestamp' in log_df.columns:
            log_df = log_df.sort_values('Timestamp', ascending=True).reset_index(drop=True)
        
        sim_start = log_df[log_df['Event'] == 'SIM_START']
        if not sim_start.empty:
            message = sim_start.iloc[0]['Message']
            import re
            rate_match = re.search(r'processing rate:\s*([\d,]+)', str(message))
            if rate_match:
                try:
                    processing_rate_html = float(rate_match.group(1).replace(',', ''))
                except:
                    pass

    if summary_df is not None:
        try:
            summary_df['Date'] = pd.to_datetime(summary_df['Date'], format='%d/%m/%Y', errors='coerce')
        except Exception:
            try:
                summary_df['Date'] = pd.to_datetime(summary_df['Date'], errors='coerce')
            except Exception:
                pass

    if snapshot_df is not None:
        first_col = snapshot_df.columns[0]
        try:
            timestamps = pd.to_datetime(snapshot_df[first_col], format='%d/%m/%Y %H:%M', errors='coerce')
            if timestamps.isna().all():
                timestamps = pd.to_datetime(snapshot_df[first_col], errors='coerce')
            
            if timestamps.notna().sum() > 0:
                st.info(f"📊 Detected HORIZONTAL snapshot format: {len(snapshot_df)} time points, {len(snapshot_df.columns)-1} data columns")
                snapshot_df['_Timestamp'] = timestamps
        except Exception as e:
            st.warning(f"Could not parse timestamps from first column: {e}")

    return log_df, summary_df, cargo_df, snapshot_df, crude_mix, processing_rate_html


def get_all_tank_ids(log_df, snapshot_df):
    """
    Dynamically detects the *list* of all existing tank IDs.
    The SNAPSHOT file is the *only* source of truth for this,
    as other files (like log_df) may contain "ghost" columns.
    """
    detected_tanks = set()
    
    # We ONLY check snapshot_df. We IGNORE log_df for this.
    if snapshot_df is not None:
        # Find columns like "Tank1", "Tank25", "Tank603"
        tank_cols = [col for col in snapshot_df.columns if re.match(r'^Tank\d+$', col)]
        for col in tank_cols:
            try:
                detected_tanks.add(int(col[4:]))
            except ValueError:
                continue
                
        # Also check "State" columns
        state_cols = [col for col in snapshot_df.columns if re.match(r'^State\d+$', col)]
        for col in state_cols:
            try:
                detected_tanks.add(int(col[5:]))
            except ValueError:
                continue
    
    if not detected_tanks:
        st.warning("Could not detect any tanks from tank_snapshots.csv. Display may be empty.")
        return [] # No tanks found
        
    return sorted(list(detected_tanks)) # Return a sorted list [1, 2, ... 13, 25, 204, 603]


def get_tank_status(log_df, snapshot_df, timestamp, all_tank_ids):
    """Get tank status at specific timestamp - READS FROM HORIZONTAL SNAPSHOT FORMAT"""
    tank_status = {}
    
    # Method 1: Try to get status from log_df
    if log_df is not None and not log_df.empty:
        filtered = log_df[log_df['Timestamp'] <= timestamp].copy()
        if not filtered.empty:
            latest_row = filtered.iloc[-1]
            # Read by column name
            for tank_id in all_tank_ids:
                col_name = f'Tank{tank_id}'
                if col_name in latest_row.index:
                    status = latest_row[col_name]
                    if pd.notna(status) and isinstance(status, str):
                        tank_status[tank_id] = status.strip().upper()

    # Method 2: Read from HORIZONTAL snapshot format (This is the CRITICAL fix)
    if snapshot_df is not None and not snapshot_df.empty and '_Timestamp' in snapshot_df.columns:
        matched_rows = snapshot_df[snapshot_df['_Timestamp'] <= timestamp]
        
        if matched_rows.empty:
            latest_snapshot = snapshot_df.iloc[0]
        else:
            latest_snapshot = matched_rows.iloc[-1]
        
        # --- START FIX: Read status by column name (e.g., "State25") ---
        for tank_id in all_tank_ids:
            status_col_name = f'State{tank_id}'
            
            # Try to get status from snapshot *only if not already found in log*
            if tank_id not in tank_status and status_col_name in latest_snapshot.index:
                value = latest_snapshot[status_col_name]
                if pd.notna(value) and str(value).strip():
                    tank_status[tank_id] = str(value).strip().upper()
        # --- END FIX ---
    
    # Fill in any tanks that are *still* missing (e.g., READY at start)
    for tank_id in all_tank_ids:
        if tank_id not in tank_status:
            tank_status[tank_id] = 'READY' # Default
    
    return tank_status


def get_tank_volume(snapshot_df, timestamp, tank_id):
    """
    Get tank volume from snapshots - CORRECTED for data format:
    [Timestamp, Tank1, State1, Tank2, State2, ...]
    """
    
    # If no snapshot data, or timestamp column is missing, return 0
    if snapshot_df is None or snapshot_df.empty or '_Timestamp' not in snapshot_df.columns:
        return 0
    
    # --- START CORRECTED LOGIC ---

    # 1. Find the latest snapshot row based on the selected timestamp
    matched_rows = snapshot_df[snapshot_df['_Timestamp'] <= timestamp]
    
    if matched_rows.empty:
        # If no row is at or before the timestamp, use the very first row
        latest_snapshot = snapshot_df.iloc[0]
    else:
        # Otherwise, use the last row that matches (the most recent one)
        latest_snapshot = matched_rows.iloc[-1]
    
    # 2. Define the *exact* column name to find, based on your file's format
    # (e.g., for tank_id 5, this will be "Tank5")
    tank_col_name = f'Tank{tank_id}'
    
    # 3. Check if this column exists in the snapshot data
    if tank_col_name in latest_snapshot.index:
        # Get the value from that specific column
        value = latest_snapshot[tank_col_name]
        
        if pd.isna(value):
            return 0
        
        # Clean the value (remove commas) and convert to float
        vol_str = str(value).replace(',', '').replace(' ', '').strip()
        
        try:
            volume = float(vol_str)
            return max(0, volume)  # Return the volume
        except ValueError:
            # The value was not a number (e.g., it might have been a status string)
            return 0
    
    # 4. If the column (e.g., "Tank5") was not found, return 0
    return 0
    # --- END CORRECTED LOGIC ---

def get_crude_mix(crude_mix_dict):
    """Get crude mix from HTML input data"""
    return crude_mix_dict if crude_mix_dict else None

def display_tank_grid(tank_status, snapshot_df, timestamp, all_tank_ids):
    """Display tank status grid with dynamic layout based on number of tanks"""
    num_tanks = len(all_tank_ids) # Get the *count* of real tanks
    st.subheader(f"🛢️ Tank Status Grid - {num_tanks} Tanks")
    st.caption("Move the time slider above to see tank status changes over time")
    
    # Calculate optimal grid layout
    if num_tanks <= 4:
        cols_per_row = num_tanks
    elif num_tanks <= 9:
        cols_per_row = 3
    elif num_tanks <= 16:
        cols_per_row = 4
    elif num_tanks <= 25:
        cols_per_row = 5
    else:
        cols_per_row = 6  # Max 6 columns for readability
    
    num_rows = math.ceil(num_tanks / cols_per_row)
    
    # Create dynamic grid
    # --- START FIX: Loop over the *list* of tank IDs ---
    tank_index = 0 # Use an index to iterate over the list
    for row in range(num_rows):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            if tank_index < num_tanks:
                # Get the *actual* tank ID from the list
                tank_id = all_tank_ids[tank_index] 
                
                with cols[col_idx]:
                    state = tank_status.get(tank_id, 'READY')
                    color = STATE_COLORS.get(state, '#6b7280')
                    volume = get_tank_volume(snapshot_df, timestamp, tank_id)
                    
                    # Adjust font sizes based on number of tanks for better fit
                    if num_tanks <= 16:
                        tank_font_size = 24
                        state_font_size = 16
                        volume_font_size = 14
                        padding = "20px"
                    elif num_tanks <= 25:
                        tank_font_size = 20
                        state_font_size = 14
                        volume_font_size = 12
                        padding = "15px"
                    else:
                        tank_font_size = 18
                        state_font_size = 12
                        volume_font_size = 11
                        padding = "10px"
                    
                    # Display tank card with better formatting
                    st.markdown(f"""
                    <div style='background-color: {color}; 
                                padding: {padding}; 
                                border-radius: 12px; 
                                text-align: center; 
                                color: white; 
                                margin: 3px;
                                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                                min-height: 100px;'>
                        <div style='font-size: {tank_font_size}px; font-weight: bold; margin-bottom: 5px;'>Tank {tank_id}</div>
                        <div style='font-size: {state_font_size}px; margin: 5px 0; background: rgba(255,255,255,0.2); 
                                    padding: 3px; border-radius: 5px;'>{state}</div>
                        <div style='font-size: {volume_font_size}px; font-weight: bold;'>{volume:,.0f} bbl</div>
                    </div>
                    """, unsafe_allow_html=True)
                tank_index += 1 # Move to the next tank in the list
    # --- END FIX ---


def display_crude_mix(crude_mix_dict):
    """Display crude mix table showing crude names and percentages"""
    crude_data = get_crude_mix(crude_mix_dict)
    
    if crude_data and len(crude_data) > 0:
        st.subheader("🛢️ Crude Mix Composition")
        
        # Create a dataframe for display
        mix_df = pd.DataFrame([
            {"Crude Name": crude, "Percentage (%)": value}
            for crude, value in crude_data.items()
        ])
        
        # Display in a nice table
        col1, col2 = st.columns([2, 3])
        with col1:
            st.dataframe(mix_df, width='stretch', hide_index=True)
        
        with col2:
            # If percentages are numeric, show a pie chart
            try:
                numeric_values = [float(v) if isinstance(v, (int, float)) else float(str(v).replace('%', '').strip()) 
                                for v in crude_data.values()]
                
                if sum(numeric_values) > 0:
                    import plotly.graph_objects as go
                    fig = go.Figure(data=[go.Pie(
                        labels=list(crude_data.keys()),
                        values=numeric_values,
                        hole=0.3
                    )])
                    fig.update_layout(
                        title='Crude Mix Distribution',
                        height=300,
                        showlegend=True
                    )
                    st.plotly_chart(fig, config={'displayModeBar': True}, use_container_width=True)
            except:
                # If can't create chart, just show the table
                pass

def main():
    st.title("🛢️ Crude Oil Tank Simulation Dashboard")
    st.markdown("### Dynamic Multi-Tank System Monitor")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Data Source")
        st.info("Data is loaded directly from the Flask app.")
        
        if st.button("🔄 Reload Data", type="primary", use_container_width=True):
            st.rerun()
        
        st.markdown("---")
    # Load data
    log_df, summary_df, cargo_df, snapshot_df, crude_mix, processing_rate_html = load_data()
    
    # Processing rate configuration - after loading data
    with st.sidebar:
        st.markdown("---")
        st.header("⚙️ Configuration")
        
        # Processing rate input - read-only, from HTML
        if processing_rate_html:
            st.metric("Processing Rate (bbl/day)", f"{processing_rate_html:,.0f}", help="From simulation configuration")
            processing_rate_input = processing_rate_html
        else:
            st.warning("No processing rate found. Using default.")
            processing_rate_input = 50000.0
        
        st.markdown("---")
        
        # Display data timestamp from filename
        if log_df is not None and not log_df.empty:
            # Parse timestamp from filename (format: simulation_log_YYYYMMDD_HHMMSS.csv)
            try:
                log_files = [f for f in os.listdir(folder_path) if f.startswith('simulation_log_') and f.endswith('.csv')]
                if log_files:
                    latest_file = sorted(log_files)[-1]
                    # Extract timestamp from filename
                    timestamp_str = latest_file.replace('simulation_log_', '').replace('.csv', '')
                    # Parse format: YYYYMMDD_HHMMSS
                    file_timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    st.success(f"📅 Data loaded: {file_timestamp.strftime('%d/%m/%Y %H:%M:%S')}")
            except:
                # Fallback to log data timestamp
                latest_timestamp = log_df['Timestamp'].max()
                st.success(f"📅 Data loaded: {latest_timestamp.strftime('%d/%m/%Y %H:%M')}")
    
    if log_df is None and snapshot_df is None:
        st.error("❌ No data files found. Please check the folder path.")
        return
    
    # Initialize session state for selected time
    if 'selected_time' not in st.session_state:
        if log_df is not None and not log_df.empty:
            st.session_state.selected_time = pd.Timestamp(log_df['Timestamp'].min()).to_pydatetime()
        elif snapshot_df is not None and '_Timestamp' in snapshot_df.columns:
            st.session_state.selected_time = pd.Timestamp(snapshot_df['_Timestamp'].min()).to_pydatetime()
        else:
            st.session_state.selected_time = datetime.now()
    
    # Get time range - Convert all to datetime.datetime for consistency
    min_time = st.session_state.selected_time
    max_time = st.session_state.selected_time
    
    if log_df is not None and not log_df.empty:
        min_time = pd.Timestamp(log_df['Timestamp'].min()).to_pydatetime()
        max_time = pd.Timestamp(log_df['Timestamp'].max()).to_pydatetime()
    elif snapshot_df is not None and '_Timestamp' in snapshot_df.columns:
        min_time = pd.Timestamp(snapshot_df['_Timestamp'].min()).to_pydatetime()
        max_time = pd.Timestamp(snapshot_df['_Timestamp'].max()).to_pydatetime()
    
    # Ensure min and max are different (add 1 hour if same)
    if min_time == max_time:
        max_time = min_time + timedelta(hours=1)
    
    # Time selector with dropdowns
    st.markdown("### ⏰ Select Time Point")
    
    # Get time range from data
    if log_df is not None and not log_df.empty:
        data_min_time = log_df['Timestamp'].min()
        data_max_time = log_df['Timestamp'].max()
    elif snapshot_df is not None and '_Timestamp' in snapshot_df.columns:
        data_min_time = snapshot_df['_Timestamp'].min()
        data_max_time = snapshot_df['_Timestamp'].max()
    else:
        data_min_time = min_time
        data_max_time = max_time
    
    # Generate all dates in range
    current_date = data_min_time.date()
    end_date = data_max_time.date()
    date_list = []
    while current_date <= end_date:
        date_list.append(current_date)
        current_date += timedelta(days=1)
    
    date_options = [d.strftime('%d/%m/%Y') for d in date_list]
    
    # Create two columns for date and time dropdowns
    col1, col2 = st.columns(2)
    
    with col1:
        # Date dropdown
        selected_date_str = st.selectbox(
            "📅 Select Date",
            options=date_options,
            index=0,
            key='date_selector',
            help="Select the date"
        )
        selected_date = datetime.strptime(selected_date_str, '%d/%m/%Y').date()
    
    with col2:
        # Time input as a text box
        selected_time_str = st.text_input(
            "🕐 Select Time (HH MM)",
            value="00 00",  # Default to 00:00
            key='time_selector',
            help="Type the time in 24-hour HH MM format (e.g., 14 30)"
        )

        # Parse the HH MM string
        try:
            # Replace common separators with a space, then split
            parts = selected_time_str.replace(':', ' ').replace('-', ' ').split()
            if len(parts) == 2:
                hour = int(parts[0])
                minute = int(parts[1])
                # This will raise ValueError if hour > 23 or minute > 59
                selected_time_obj = datetime.strptime(f"{hour}:{minute}", "%H:%M").time()
            else:
                # Handle single number input, e.g., "10" -> 10:00
                if len(parts) == 1 and parts[0].isdigit():
                     hour = int(parts[0])
                     selected_time_obj = datetime.strptime(f"{hour}:00", "%H:00").time()
                else:
                    raise ValueError("Invalid format")
        except Exception:
            # If parsing fails, default to 00:00 and warn the user
            st.warning(f"Invalid time: '{selected_time_str}'. Defaulting to 00:00.")
            selected_time_obj = datetime.strptime("00:00", "%H:%M").time()
        
        # Combine date and time
        selected_time = datetime.combine(selected_date, selected_time_obj)

    # Convert to datetime if it's a pandas Timestamp
    if isinstance(selected_time, pd.Timestamp):
        selected_time = selected_time.to_pydatetime()
    
    st.session_state.selected_time = selected_time
    
    # --- START FIX: Use new list-based logic ---
    
    # 1. Get the *list* of all real tank IDs
    all_tank_ids = get_all_tank_ids(log_df, snapshot_df)
    num_tanks = len(all_tank_ids) # This is the *count* of tanks
    
    # 2. Get status for *only* those tanks
    tank_status = get_tank_status(log_df, snapshot_df, selected_time, all_tank_ids)
        
    # 3. Display info about detected tanks
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📊 System has **{num_tanks} tanks**")
    # --- END FIX ---
        
    with col2:
        st.info(f"🕐 Viewing: **{selected_time.strftime('%H:%M')}**")
    with col3:
        st.info(f"📅 Date: **{selected_time.strftime('%d/%m/%Y')}**")
    
    # Key metrics
    st.markdown("---")
    
    # Calculate real-time certified stock at selected time
    certified_stock_at_time = 0.0
    for tank_id in all_tank_ids: # Use the correct list
        if tank_status.get(tank_id) in ['READY', 'FEEDING']:
            volume = get_tank_volume(snapshot_df, selected_time, tank_id)
            certified_stock_at_time += volume
    
    # Convert to MMbbl
    certified_stock_mmbl = certified_stock_at_time / 1_000_000
    
    # Display certified stock for selected time prominently
    st.markdown("### 📊 Certified Stock at Selected Time")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Certified Stock (MMbbl)", f"{certified_stock_mmbl:.3f}")
    with col2:
        if processing_rate_input and processing_rate_input > 0:
            days_remaining = certified_stock_at_time / processing_rate_input
            st.metric("Days Remaining", f"{days_remaining:.2f}")
        else:
            st.metric("Days Remaining", "N/A")
    with col3:
        ready_feeding_count = sum(1 for s in tank_status.values() if s in ['READY', 'FEEDING'])
        st.metric("Ready + Feeding Tanks", f"{ready_feeding_count}")
    
    st.markdown("---")
    
    # Calculate metrics
    metrics = {}
    for state in STATE_COLORS.keys():
        count = sum(1 for s in tank_status.values() if s == state)
        if count > 0:
            metrics[state] = count
    
    # Display metrics dynamically based on what states are present
    if metrics:
        cols = st.columns(min(len(metrics), 6))  # Max 6 columns
        for idx, (state, count) in enumerate(metrics.items()):
            with cols[idx % len(cols)]:
                color = STATE_COLORS.get(state, '#6b7280')
                # Use emoji based on state
                emoji = {
                    'READY': '🟢',
                    'FEEDING': '🔵',
                    'FILLING': '🟠',
                    'EMPTY': '🔴',
                    'FILLED': '🟣',
                    'SETTLING': '🟡',
                    'LAB': '🔷',
                    'SUSPENDED': '⚫',
                    'IDLE': '⚪'
                }.get(state, '⚪')
                st.metric(f"{emoji} {state}", count)
    
    st.markdown("---")
    
    # Tank grid - now passing snapshot_df and the *list* of tanks
    display_tank_grid(tank_status, snapshot_df, selected_time, all_tank_ids)
    
    st.markdown("---")
    
    # Charts in tabs
    tabs = ["🛢️ Crude Mix", "📋 Events Log"]
    if snapshot_df is not None and not snapshot_df.empty:
        tabs.append("📊 Certified Stock")
    if cargo_df is not None:
        tabs.append("🚢 Cargo Report")
    if summary_df is not None:
        tabs.append("📈 Daily Summary")
    
    tab_objects = st.tabs(tabs)
    
    tab_idx = 0
    
    # Crude Mix tab
    with tab_objects[tab_idx]:
        if crude_mix and len(crude_mix) > 0:
            st.subheader("🛢️ Crude Mix Target Configuration")
            
            # Create a dataframe for display
            mix_df = pd.DataFrame([
                {"Crude Name": crude, "Percentage (%)": value}
                for crude, value in crude_mix.items()
            ])
            
            # Display table
            st.dataframe(mix_df, width='stretch', hide_index=True)
            
            # Display pie chart
            try:
                numeric_values = list(crude_mix.values())
                if sum(numeric_values) > 0:
                    import plotly.graph_objects as go
                    fig = go.Figure(data=[go.Pie(
                        labels=list(crude_mix.keys()),
                        values=numeric_values,
                        hole=0.3
                    )])
                    fig.update_layout(
                        title='Crude Mix Distribution',
                        height=400,
                        showlegend=True
                    )
                    st.plotly_chart(fig, config={'displayModeBar': True}, use_container_width=True)
            except:
                pass
        else:
            st.warning("No crude mix data found in simulation log READY_1 events.")
    
    # streamlit_app.py (REPLACEMENT for lines 657-737)

    tab_idx += 1
    
    # Events Log tab
    with tab_objects[tab_idx]:
        if log_df is not None and not log_df.empty:
            st.subheader("All Events")
            
            # --- START FIX: Correct sorting and full log search ---
            
            # 1. Create a copy of the full log_df.
            # (log_df is already sorted by a true datetime in the load_data function)
            display_df = log_df.copy()
            
            # 2. Search functionality
            col1, col2 = st.columns([3, 1])
            with col1:
                search = st.text_input("🔍 Search events", "", placeholder="Type to filter all events...")
            with col2:
                show_all = st.checkbox("Show all columns", value=False)
            
            if search:
                # 3. Apply search mask to the ENTIRE log (before formatting timestamp)
                mask = pd.Series([False] * len(display_df))
                for col in display_df.columns:
                    if col == 'Timestamp': # Skip search on the datetime object
                        continue
                    if display_df[col].dtype == 'object':
                        mask |= display_df[col].str.contains(search, case=False, na=False)
                    else:
                        # Convert other columns (like numbers) to string to search
                        mask |= display_df[col].astype(str).str.contains(search, case=False, na=False)
                display_df = display_df[mask]
            else:
                # 4. If NOT searching, *then* limit the view to the last 1000 lines for performance.
                #    (You can change 1000 to whatever limit you want, or remove it to show all)
                display_df = display_df.tail(1000)
            
            # 5. Determine which columns to display
            if show_all:
                display_cols = list(display_df.columns)
            else:
                possible_cols = ['Timestamp', 'Level', 'Event', 'Tank', 'Cargo', 'Message']
                display_cols = [col for col in possible_cols if col in display_df.columns]
            
            # 6. Format timestamp to string *AFTER* all sorting/filtering is done
            if 'Timestamp' in display_df.columns:
                display_df['Timestamp'] = display_df['Timestamp'].dt.strftime('%d/%m/%Y %H:%M')
            
            # --- END FIX ---
            
            if not display_df.empty:
                st.markdown("""
                <style>
                    .dataframe {
                        font-size: 11px !important;
                    }
                    .dataframe td, .dataframe th {
                        padding: 2px 4px !important;
                        font-size: 11px !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                # 7. Display the DataFrame. It is already sorted.
                #    DO NOT call .sort_values() here.
                st.dataframe(
                    display_df[display_cols].reset_index(drop=True), # This is now chronologically correct
                    width='stretch',
                    height=400,
                    hide_index=True
                )
            else:
                st.info("No events found matching your criteria")
        else:
            st.warning("No event log data available")
    
    tab_idx += 1
    
    # Inventory tab - NOW USING SNAPSHOTS
    if snapshot_df is not None and not snapshot_df.empty and tab_idx < len(tab_objects):
        with tab_objects[tab_idx]:
            st.subheader("Certified Stock Over Time")
            
            if '_Timestamp' in snapshot_df.columns:
                # Get date range from snapshots
                data_min_time = snapshot_df['_Timestamp'].min()
                data_max_time = snapshot_df['_Timestamp'].max()
                
                # Generate date list
                current_date = data_min_time.date()
                end_date = data_max_time.date()
                date_list = []
                while current_date <= end_date:
                    date_list.append(current_date)
                    current_date += timedelta(days=1)
                
                date_options = [d.strftime('%d/%m/%Y') for d in date_list]
                
                # Create two columns for date and time dropdowns (SAME AS SELECT TIME POINT)
                st.markdown("#### Select Date and Time to View Certified Stock")
                col1, col2 = st.columns(2)
                
                with col1:
                    # Date dropdown
                    selected_inv_date_str = st.selectbox(
                        "📅 Select Date",
                        options=date_options,
                        index=len(date_options)-1,  # Default to last date
                        key='inv_date_selector',
                        help="Select the date"
                    )
                    selected_inv_date = datetime.strptime(selected_inv_date_str, '%d/%m/%Y').date()
                
                with col2:
                    # Time input as a text box
                    selected_inv_time_str = st.text_input(
                        "🕐 Select Time (HH MM)",
                        value="23 59",  # Default to 23:59
                        key='inv_time_selector',
                        help="Type the time in 24-hour HH MM format (e.g., 14 30)"
                    )

                    # Parse the HH MM string
                    try:
                        # Replace common separators with a space, then split
                        parts = selected_inv_time_str.replace(':', ' ').replace('-', ' ').split()
                        if len(parts) == 2:
                            hour = int(parts[0])
                            minute = int(parts[1])
                            # This will raise ValueError if hour > 23 or minute > 59
                            selected_time_obj = datetime.strptime(f"{hour}:{minute}", "%H:%M").time()
                        else:
                            if len(parts) == 1 and parts[0].isdigit():
                                 hour = int(parts[0])
                                 selected_time_obj = datetime.strptime(f"{hour}:00", "%H:00").time()
                            else:
                                raise ValueError("Invalid format")
                    except Exception:
                        # If parsing fails, default to 23:59 and warn the user
                        st.warning(f"Invalid time: '{selected_inv_time_str}'. Defaulting to 23:59.")
                        selected_time_obj = datetime.strptime("23:59", "%H:%M").time()
                    
                    # Combine date and time
                    selected_inv_datetime = datetime.combine(selected_inv_date, selected_time_obj)
                
                # Calculate certified stock for ALL snapshots (for the graph)
                timestamps = []
                certified_stocks = []
                
                for idx, row in snapshot_df.iterrows():
                    timestamp = row['_Timestamp']
                    certified_stock = 0.0
                    
                    # Sum READY and FEEDING tank volumes (SAME AS SELECT TIME POINT)
                    for tank_id in all_tank_ids: # Use the correct list
                        state_col = f'State{tank_id}'
                        tank_col = f'Tank{tank_id}'
                        
                        if state_col in row.index and tank_col in row.index:
                            state = str(row[state_col]).strip().upper()
                            
                            if state in ['READY', 'FEEDING']:
                                volume_str = str(row[tank_col]).replace(',', '').strip()
                                try:
                                    volume = float(volume_str)
                                    certified_stock += volume
                                except:
                                    pass
                    
                    timestamps.append(timestamp)
                    certified_stocks.append(certified_stock / 1_000_000)  # Convert to MMbbl
                
                # Create dataframe for plotting
                chart_df = pd.DataFrame({
                    'Timestamp': timestamps,
                    'Certified Stock (MMbbl)': certified_stocks
                })
                
                # Get certified stock at selected date/time
                matched_rows = chart_df[chart_df['Timestamp'] <= selected_inv_datetime]
                if not matched_rows.empty:
                    selected_row = matched_rows.iloc[-1]
                    selected_certified_stock = selected_row['Certified Stock (MMbbl)']
                    selected_timestamp = selected_row['Timestamp']
                else:
                    selected_certified_stock = 0.0
                    selected_timestamp = selected_inv_datetime
                
                # Create line chart
                fig = px.line(
                    chart_df,
                    x='Timestamp',
                    y='Certified Stock (MMbbl)',
                    title='Certified Stock Timeline',
                    labels={'Certified Stock (MMbbl)': 'Certified Stock (Million Barrels)', 'Timestamp': 'Date & Time'}
                )
                
                # Add marker for selected date/time
                fig.add_scatter(
                    x=[selected_timestamp],
                    y=[selected_certified_stock],
                    mode='markers',
                    marker=dict(size=15, color='red', symbol='circle'),
                    name='Selected Point',
                    showlegend=True
                )
                
                fig.update_xaxes(tickformat='%d/%m/%Y', tickangle=-45)
                fig.update_layout(height=400, hovermode='x unified')
                st.plotly_chart(fig, config={'displayModeBar': True}, use_container_width=True)
                
                # Show certified stock stats
                st.markdown("""
                <style>
                    div[data-testid="stMetric"],
                    div[data-testid="metric-container"],
                    .stMetric {
                        background-color: #000000 !important;
                        color: white !important;
                        padding: 20px !important;
                        border-radius: 10px !important;
                        border: 1px solid #333 !important;
                    }
                    div[data-testid="stMetric"] label,
                    div[data-testid="stMetric"] > div > div > div {
                        color: #ffffff !important;
                        background-color: transparent !important;
                    }
                    div[data-testid="stMetric"] [data-testid="stMetricValue"],
                    div[data-testid="stMetric"] div[data-testid="stMarkdownContainer"] {
                        color: #ffffff !important;
                        background-color: transparent !important;
                    }
                    div[data-testid="stMetric"] * {
                        background-color: transparent !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Certified Stock (Selected Date/Time)", f"{selected_certified_stock:.2f} MMbbl")
                with col2:
                    st.metric("Average (All Time)", f"{chart_df['Certified Stock (MMbbl)'].mean():.2f} MMbbl")
                with col3:
                    st.metric("Max (All Time)", f"{chart_df['Certified Stock (MMbbl)'].max():.2f} MMbbl")
                
                # Calculate days remaining
                st.markdown("---")
                
                if processing_rate_input and processing_rate_input > 0:
                    selected_certified_stock_bbl = selected_certified_stock * 1_000_000
                    days_remaining = selected_certified_stock_bbl / processing_rate_input
                    st.info(f"📊 **Certified stock will last for {days_remaining:.2f} days** (at processing rate of {processing_rate_input:,.0f} bbl/day)")
                else:
                    st.warning("⚠️ Please enter a valid processing rate in the sidebar")
            else:
                st.warning("No snapshot data available")
        tab_idx += 1
    
    # Cargo Report tab
    if cargo_df is not None and tab_idx < len(tab_objects):
        with tab_objects[tab_idx]:
            st.subheader("Cargo Schedule")
            
            # Format berth gap hours as decimals if the column exists
            cargo_display = cargo_df.copy()
            
            # Remove duplicate rows (keep first occurrence)
            cargo_display = cargo_display.drop_duplicates()
            
            # Remove Cargo Type column if it exists
            columns_to_remove = ['Cargo Type', 'CARGO TYPE', 'Cargo_Type', 'cargo_type']
            for col in columns_to_remove:
                if col in cargo_display.columns:
                    cargo_display = cargo_display.drop(columns=[col])
            
            if 'BERTH GAP(hrs)' in cargo_display.columns:
                cargo_display['BERTH GAP(hrs)'] = cargo_display['BERTH GAP(hrs)'].apply(
                    lambda x: f"{float(x):.2f}" if pd.notna(x) else x
                )
            
            st.dataframe(cargo_display,width='content', height=400)
        tab_idx += 1
    
    # Daily Summary tab
    if summary_df is not None and tab_idx < len(tab_objects):
        with tab_objects[tab_idx]:
            if 'Date' in summary_df.columns:
                st.subheader("Daily Processing Summary")
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.dataframe(summary_df,width='stretch', height=400)
                
                with col2:
                    if 'Processing (bbl)' in summary_df.columns:
                        # Convert to numeric, removing commas
                        processing_values = pd.to_numeric(summary_df['Processing (bbl)'].astype(str).str.replace(',', ''), errors='coerce')
                        st.metric("Total Processed", 
                                f"{processing_values.sum():,.0f} bbl")
                        st.metric("Daily Average", 
                                f"{processing_values.mean():,.0f} bbl")
                
                # Daily chart
                valid_summary_dates = summary_df['Date'].dropna()
                if not valid_summary_dates.empty and 'Processing (bbl)' in summary_df.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=summary_df.dropna(subset=['Date'])['Date'],
                        y=summary_df.dropna(subset=['Date'])['Processing (bbl)'],
                        name='Processing',
                        marker_color='#3b82f6'
                    ))
                    fig.update_layout(
                        title='Daily Processing Volume',
                        xaxis_title='Date',
                        yaxis_title='Processing (barrels)',
                        height=300
                    )
                    st.plotly_chart(fig, config={'displayModeBar': True}, use_container_width=True)

if __name__ == "__main__":
    main()