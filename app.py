import streamlit as st
import requests
import time
from datetime import datetime, timedelta
import re
import os
from dotenv import load_dotenv
from dateutil.tz import gettz, UTC

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Car Scout",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API base URL - use PORT from environment to match backend
API_PORT = int(os.getenv("PORT", 5001))
API_BASE_URL = f"http://localhost:{API_PORT}/api"

# Custom CSS - Modern, clean design
st.markdown("""
<style>
    /* Main container - White background */
    .main {
        background-color: #ffffff !important;
        color: #1a1a1a !important;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-left: 3rem;
        padding-right: 3rem;
        max-width: 1400px;
        background-color: #ffffff !important;
    }
    
    /* Sidebar styling - Light gray */
    [data-testid="stSidebar"] {
        background-color: #e9ecef !important;
        border-right: 1px solid #dee2e6;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1 {
        color: #212529 !important;
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 2rem;
        padding: 0 1rem;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] {
        margin-top: 1rem;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding: 0.75rem 1.5rem;
        font-size: 1rem;
        font-weight: 500;
        color: #212529 !important;
        border-radius: 8px;
        margin: 0.25rem 0;
        transition: all 0.2s;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] label * {
        color: #212529 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] label span {
        color: #212529 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background-color: #dee2e6;
        color: #000000 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover * {
        color: #000000 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"]:checked + label {
        background-color: #007bff;
        color: #ffffff !important;
        font-weight: 600;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"]:checked + label * {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"]:checked + label span {
        color: #ffffff !important;
    }
    
    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        background-color: #007bff;
        color: white;
        font-weight: 500;
        padding: 0.5rem 1rem;
        border: none;
        transition: all 0.2s;
    }
    
    .stButton>button:hover {
        background-color: #0056b3;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0,123,255,0.3);
    }
    
    /* Message styling */
    .message-item {
        padding: 0.875rem 1.125rem;
        border-radius: 16px;
        margin-bottom: 0.75rem;
        max-width: 75%;
        word-wrap: break-word;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .message-item.inbound {
        background-color: #f1f3f5;
        color: #212529;
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }
    
    .message-item.outbound {
        background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
        color: #ffffff;
        margin-left: auto;
        border-bottom-right-radius: 4px;
    }
    
    /* Thread list styling */
    .thread-item {
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .thread-item:hover {
        background-color: #f8f9fa;
        border-color: #007bff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Info boxes */
    .stInfo {
        background-color: #e7f3ff;
        border-left: 4px solid #007bff;
        padding: 1rem;
        border-radius: 4px;
    }
    
    /* Main content text visibility - Dark text on white */
    .main p, .main div, .main span, .main label {
        color: #212529 !important;
    }
    
    /* Titles */
    h1 {
        color: #212529 !important;
        font-weight: 700;
        margin-bottom: 1.5rem;
    }
    
    h2 {
        color: #212529 !important;
        font-weight: 600;
    }
    
    h3 {
        color: #212529 !important;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    /* Captions and labels */
    .stCaption {
        color: #6c757d !important;
    }
    
    /* Metric labels and values - Dark text */
    [data-testid="stMetricLabel"] {
        color: #6c757d !important;
    }
    
    [data-testid="stMetricValue"] {
        color: #212529 !important;
    }
    
    [data-testid="stMetricValue"] > div {
        color: #212529 !important;
    }
    
    /* All text elements in main area */
    .element-container, .stMarkdown, .stText {
        color: #212529 !important;
    }
    
    /* Selectbox text */
    [data-baseweb="select"] {
        color: #212529 !important;
    }
    
    [data-baseweb="select"] span {
        color: #212529 !important;
    }
    
    /* Info boxes */
    .stInfo {
        background-color: #e7f3ff;
        border-left: 4px solid #007bff;
        padding: 1rem;
        border-radius: 4px;
        color: #004085 !important;
    }
    
    .stInfo p, .stInfo div {
        color: #004085 !important;
    }
    
    /* Error boxes */
    .stError {
        color: #721c24 !important;
    }
    
    .stError p, .stError div {
        color: #721c24 !important;
    }
    
    /* Dataframe styling */
    .dataframe {
        color: #212529 !important;
        background-color: #ffffff !important;
    }
    
    /* Override Streamlit's default dark theme */
    .stApp {
        background-color: #ffffff !important;
    }
    
    /* All Streamlit text elements */
    .stMarkdown, .stText, .stDataFrame, .stSelectbox, .stButton {
        color: #212529 !important;
    }
    
    /* Column containers */
    [data-testid="column"] {
        background-color: transparent !important;
    }
    
    /* Ensure all text in main is dark */
    .main * {
        color: inherit;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Status indicator */
    .status-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }
    
    .status-online {
        background-color: #28a745;
    }
    
    .status-offline {
        background-color: #dc3545;
    }
    
    /* Calendar styling */
    .calendar-container {
        border: 2px solid #dee2e6;
        border-radius: 8px;
        overflow: hidden;
        background-color: #ffffff;
    }
    
    .calendar-header {
        display: grid;
        grid-template-columns: 80px repeat(7, 1fr);
        background-color: #f8f9fa;
        border-bottom: 2px solid #dee2e6;
    }
    
    .calendar-header-cell {
        padding: 0.75rem;
        text-align: center;
        font-weight: 600;
        border-right: 1px solid #dee2e6;
        color: #212529;
    }
    
    .calendar-header-cell:last-child {
        border-right: none;
    }
    
    .calendar-time-cell {
        padding: 0.5rem;
        text-align: right;
        font-size: 0.85rem;
        color: #6c757d;
        border-right: 1px solid #dee2e6;
        border-bottom: 1px solid #e9ecef;
        background-color: #f8f9fa;
        min-height: 60px;
    }
    
    .calendar-day-cell {
        padding: 0.5rem;
        border-right: 1px solid #dee2e6;
        border-bottom: 1px solid #e9ecef;
        min-height: 60px;
        position: relative;
    }
    
    .calendar-day-cell:last-child {
        border-right: none;
    }
    
    .calendar-row {
        display: grid;
        grid-template-columns: 80px repeat(7, 1fr);
    }
    
    .visit-item {
        background-color: #007bff;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        margin: 0.25rem 0;
        font-size: 0.75rem;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    
    .visit-item:hover {
        background-color: #0056b3;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)


def format_phone_number(phone):
    """Format phone number for display"""
    cleaned = re.sub(r'\D', '', phone)
    if len(cleaned) == 11 and cleaned[0] == '1':
        return f"+1 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"
    elif len(cleaned) == 10:
        return f"({cleaned[0:3]}) {cleaned[3:6]}-{cleaned[6:]}"
    return phone


def format_time(timestamp):
    """Format timestamp for display"""
    if not timestamp:
        return ''
    
    try:
        if isinstance(timestamp, str):
            # Try parsing ISO format
            try:
                if 'T' in timestamp:
                    date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    # Try other formats
                    date = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            except:
                # Try with timezone
                try:
                    date = datetime.fromisoformat(timestamp)
                except:
                    return timestamp[:10] if len(timestamp) >= 10 else timestamp
        else:
            date = timestamp
        
        # Remove timezone info for comparison
        if hasattr(date, 'tzinfo') and date.tzinfo:
            date = date.replace(tzinfo=None)
        
        now = datetime.now()
        diff = (now - date).total_seconds()
        
        minutes = int(diff / 60)
        hours = int(diff / 3600)
        days = int(diff / 86400)
        
        if minutes < 1:
            return 'Just now'
        if minutes < 60:
            return f'{minutes}m ago'
        if hours < 24:
            return f'{hours}h ago'
        if days < 7:
            return f'{days}d ago'
        return date.strftime('%m/%d/%Y')
    except Exception as e:
        # Return a simplified version if parsing fails
        if isinstance(timestamp, str):
            return timestamp[:10] if len(timestamp) >= 10 else timestamp
        return ''


def check_api_connection():
    """Check if the API is reachable"""
    try:
        response = requests.get(f"{API_BASE_URL}", timeout=2)
        return response.status_code == 200
    except:
        return False


# Sidebar navigation
st.sidebar.markdown("# Car Scout")
page = st.sidebar.radio(
    "Navigation",
    ["Home", "Listings"],
    label_visibility="collapsed"
)

# API Connection Status
api_connected = check_api_connection()
status_color = "🟢" if api_connected else "🔴"
status_text = "Connected" if api_connected else "Disconnected"

# Route to appropriate page
if page == "Home":
    st.title("Car Scout Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("API Status", status_text)
    
    with col2:
        if api_connected:
            try:
                db_response = requests.get(f"{API_BASE_URL}/test-db", timeout=2)
                if db_response.status_code == 200:
                    db_data = db_response.json()
                    db_status = "🟢 Connected" if db_data.get("connected") else "🔴 Disconnected"
                    st.metric("Database", db_status)
                else:
                    st.metric("Database", "🔴 Unknown")
            except:
                st.metric("Database", "🔴 Unknown")
        else:
            st.metric("Database", "—")
    
    with col3:
        if api_connected:
            try:
                threads_response = requests.get(f"{API_BASE_URL}/threads", timeout=2)
                listings_response = requests.get(f"{API_BASE_URL}/car-listings", timeout=2)
                thread_count = len(threads_response.json()) if threads_response.status_code == 200 else 0
                listing_count = len(listings_response.json()) if listings_response.status_code == 200 else 0
                st.metric("Total Threads", thread_count)
                st.metric("Total Listings", listing_count)
            except:
                st.metric("Total Threads", "—")
                st.metric("Total Listings", "—")
        else:
            st.metric("Total Threads", "—")
            st.metric("Total Listings", "—")
    
    if not api_connected:
        st.error(f"⚠️ Cannot connect to backend API at {API_BASE_URL}. Please ensure the backend server is running on port {API_PORT}.")
        st.info("To start the backend, run: `python3 server.py` or use `./start.sh`")
    
    # Calendar View Section
    st.markdown("---")
    st.markdown("### Scheduled Visits")
    
    if api_connected:
        # Week navigation
        col_nav1, col_nav2, col_nav3, col_nav4 = st.columns([1, 1, 1, 5])
        
        with col_nav1:
            if st.button("◀ Previous Week"):
                if 'calendar_week_offset' not in st.session_state:
                    st.session_state.calendar_week_offset = 0
                st.session_state.calendar_week_offset -= 1
                st.rerun()
        
        with col_nav2:
            if st.button("Today"):
                if 'calendar_week_offset' in st.session_state:
                    del st.session_state.calendar_week_offset
                st.rerun()
        
        with col_nav3:
            if st.button("Next Week ▶"):
                if 'calendar_week_offset' not in st.session_state:
                    st.session_state.calendar_week_offset = 0
                st.session_state.calendar_week_offset += 1
                st.rerun()
        
        # Calculate current week dates
        week_offset = st.session_state.get('calendar_week_offset', 0)
        today = datetime.now()
        days_since_monday = (today.weekday()) % 7
        week_start = today - timedelta(days=days_since_monday) + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)
        
        st.caption(f"Week of {week_start.strftime('%B %d, %Y')} - {week_end.strftime('%B %d, %Y')}")
        
        # Fetch visits for this week
        try:
            start_date = week_start.strftime('%Y-%m-%d')
            end_date = week_end.strftime('%Y-%m-%d')
            visits_response = requests.get(
                f"{API_BASE_URL}/visits",
                params={"start_date": start_date, "end_date": end_date},
                timeout=5
            )
            
            visits = []
            if visits_response.status_code == 200:
                visits = visits_response.json()
            
            # Create calendar grid
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_dates = [week_start + timedelta(days=i) for i in range(7)]
            
            # Group visits by day
            visits_by_day = {}
            for visit in visits:
                visit_date_str = visit.get('scheduledTime', '')
                if visit_date_str:
                    try:
                        if isinstance(visit_date_str, str):
                            # Handle ISO format with or without timezone
                            if visit_date_str.endswith('Z'):
                                visit_date = datetime.fromisoformat(visit_date_str.replace('Z', '+00:00'))
                            elif '+' in visit_date_str or visit_date_str.endswith('+00:00'):
                                visit_date = datetime.fromisoformat(visit_date_str)
                            else:
                                # Try parsing without timezone
                                visit_date = datetime.fromisoformat(visit_date_str)
                        else:
                            visit_date = visit_date_str
                        
                        # Convert to date for comparison (handle timezone-aware dates)
                        ct_tz = gettz('America/Chicago')
                        if hasattr(visit_date, 'tzinfo') and visit_date.tzinfo:
                            # Convert to Central Time if needed, then get date
                            visit_date_ct = visit_date.astimezone(ct_tz)
                            visit_date_only = visit_date_ct.date()
                        elif hasattr(visit_date, 'date'):
                            # Naive datetime - assume UTC and convert to CT
                            visit_date_ct = visit_date.replace(tzinfo=UTC).astimezone(ct_tz)
                            visit_date_only = visit_date_ct.date()
                        else:
                            # Assume it's already a date
                            visit_date_only = visit_date
                        
                        # Match with calendar days
                        for day_date in day_dates:
                            day_date_only = day_date.date() if hasattr(day_date, 'date') else day_date
                            if day_date_only == visit_date_only:
                                day_key = day_date.strftime('%Y-%m-%d')
                                if day_key not in visits_by_day:
                                    visits_by_day[day_key] = []
                                visits_by_day[day_key].append(visit)
                                break
                    except Exception as e:
                        print(f"Error parsing visit date: {e}")
                        import traceback
                        traceback.print_exc()
            
            # Organize visits by day and hour
            visits_by_day_hour = {}
            visit_id_map = {}  # Map visit IDs to visit objects for button clicks
            for day_key in visits_by_day:
                visits_by_day_hour[day_key] = {}
                for visit in visits_by_day[day_key]:
                    visit_time_str = visit.get('scheduledTime', '')
                    try:
                        if isinstance(visit_time_str, str):
                            if visit_time_str.endswith('Z'):
                                visit_time = datetime.fromisoformat(visit_time_str.replace('Z', '+00:00'))
                            elif '+' in visit_time_str or visit_time_str.endswith('+00:00'):
                                visit_time = datetime.fromisoformat(visit_time_str)
                            else:
                                visit_time = datetime.fromisoformat(visit_time_str)
                        else:
                            visit_time = visit_time_str
                        
                        # Handle timezone conversion
                        ct_tz = gettz('America/Chicago')
                        if hasattr(visit_time, 'tzinfo') and visit_time.tzinfo:
                            # Has timezone info, convert to CT
                            visit_time = visit_time.astimezone(ct_tz)
                        else:
                            # Naive datetime - assume it's UTC and convert to CT
                            visit_time = visit_time.replace(tzinfo=UTC).astimezone(ct_tz)
                        
                        hour = visit_time.hour
                        if hour not in visits_by_day_hour[day_key]:
                            visits_by_day_hour[day_key][hour] = []
                        visits_by_day_hour[day_key][hour].append(visit)
                        visit_id_map[str(visit.get('_id', ''))] = visit
                    except Exception as e:
                        print(f"Error organizing visit by hour: {e}")
            
            # Generate calendar HTML
            calendar_html = '<div class="calendar-container">'
            
            # Header row
            calendar_html += '<div class="calendar-header">'
            calendar_html += '<div class="calendar-header-cell"></div>'  # Time column header
            for day_name, day_date in zip(days, day_dates):
                is_today = day_date.date() == today.date()
                day_label = f"{day_name}<br>{day_date.strftime('%m/%d')}"
                if is_today:
                    day_label = f"{day_name}<br>{day_date.strftime('%m/%d')} (Today)"
                calendar_html += f'<div class="calendar-header-cell">{day_label}</div>'
            calendar_html += '</div>'
            
            # Hour rows (9 AM to 6 PM)
            for hour in range(9, 19):  # 9 AM to 6 PM
                hour_display = f"{hour % 12 or 12}{'AM' if hour < 12 else 'PM'}"
                calendar_html += '<div class="calendar-row">'
                calendar_html += f'<div class="calendar-time-cell">{hour_display}</div>'
                
                for day_date in day_dates:
                    day_key = day_date.strftime('%Y-%m-%d')
                    day_visits = visits_by_day_hour.get(day_key, {}).get(hour, [])
                    
                    calendar_html += '<div class="calendar-day-cell">'
                    for visit in day_visits:
                        visit_time_str = visit.get('scheduledTime', '')
                        try:
                            if isinstance(visit_time_str, str):
                                if visit_time_str.endswith('Z'):
                                    visit_time = datetime.fromisoformat(visit_time_str.replace('Z', '+00:00'))
                                elif '+' in visit_time_str or visit_time_str.endswith('+00:00'):
                                    visit_time = datetime.fromisoformat(visit_time_str)
                                else:
                                    visit_time = datetime.fromisoformat(visit_time_str)
                            else:
                                visit_time = visit_time_str
                            
                            # Handle timezone conversion
                            ct_tz = gettz('America/Chicago')
                            if hasattr(visit_time, 'tzinfo') and visit_time.tzinfo:
                                # Has timezone info, convert to CT
                                visit_time = visit_time.astimezone(ct_tz)
                            else:
                                # Naive datetime - assume it's UTC and convert to CT
                                from dateutil.tz import UTC
                                visit_time = visit_time.replace(tzinfo=UTC).astimezone(ct_tz)
                            
                            time_str = visit_time.strftime('%I:%M %p') if hasattr(visit_time, 'strftime') else str(visit_time)
                            
                            car_listing = visit.get('carListing', {})
                            car_info = ""
                            if car_listing:
                                year = car_listing.get('year', '')
                                make = car_listing.get('make', '')
                                model = car_listing.get('model', '')
                                car_info = f"{year} {make} {model}".strip()
                            
                            if not car_info:
                                car_info = "Visit"
                            
                            visit_id = str(visit.get('_id', ''))
                            visit_key = f"visit_{visit_id}"
                            # Create clickable visit item with onclick handler
                            calendar_html += f'<div class="visit-item" data-visit-id="{visit_id}" onclick="selectVisit(\'{visit_id}\')">{time_str}<br>{car_info[:15]}</div>'
                        except Exception as e:
                            print(f"Error displaying visit: {e}")
                    calendar_html += '</div>'
                
                calendar_html += '</div>'
            
            calendar_html += '</div>'
            
            # Store visit mapping in session state
            st.session_state.visit_id_map = visit_id_map
            
            # Display calendar
            st.markdown(calendar_html, unsafe_allow_html=True)
            
            # Add JavaScript to handle visit clicks and store in session state
            st.markdown("""
            <script>
                function selectVisit(visitId) {
                    // Store visit ID in a hidden input that Streamlit can read
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.id = 'selected_visit_id';
                    input.value = visitId;
                    // Remove existing if any
                    const existing = document.getElementById('selected_visit_id');
                    if (existing) existing.remove();
                    document.body.appendChild(input);
                    // Trigger a form submission or use Streamlit's communication
                    window.parent.postMessage({
                        type: 'streamlit:setFrameHeight',
                        height: document.body.scrollHeight
                    }, '*');
                }
            </script>
            """, unsafe_allow_html=True)
            
            # Check for selected visit in session state (set by JavaScript)
            # Use query params as a workaround
            if 'selected_visit_id' in st.session_state:
                visit_id = st.session_state.selected_visit_id
                if visit_id in visit_id_map:
                    st.session_state.selected_visit = visit_id_map[visit_id]
                    del st.session_state.selected_visit_id
                    st.rerun()
            
            # Modal for visit details
            if 'selected_visit' in st.session_state and st.session_state.selected_visit:
                visit = st.session_state.selected_visit
                
                # Create modal using streamlit's dialog
                with st.container():
                    st.markdown("---")
                    st.markdown("### Visit Details")
                    
                    # Visit time
                    visit_time_str = visit.get('scheduledTime', '')
                    try:
                        if isinstance(visit_time_str, str):
                            # Handle ISO format with or without timezone
                            if visit_time_str.endswith('Z'):
                                visit_time = datetime.fromisoformat(visit_time_str.replace('Z', '+00:00'))
                            elif '+' in visit_time_str or visit_time_str.endswith('+00:00'):
                                visit_time = datetime.fromisoformat(visit_time_str)
                            else:
                                visit_time = datetime.fromisoformat(visit_time_str)
                        else:
                            visit_time = visit_time_str
                        
                        # Convert to Central Time for display
                        ct_tz = gettz('America/Chicago')
                        if hasattr(visit_time, 'tzinfo') and visit_time.tzinfo:
                            visit_time = visit_time.astimezone(ct_tz)
                        else:
                            # Naive datetime - assume UTC and convert to CT
                            from dateutil.tz import UTC
                            visit_time = visit_time.replace(tzinfo=UTC).astimezone(ct_tz)
                        
                        time_display = visit_time.strftime('%A, %B %d, %Y at %I:%M %p') if hasattr(visit_time, 'strftime') else str(visit_time)
                    except Exception as e:
                        time_display = str(visit_time_str)
                        print(f"Error formatting visit time: {e}")
                    
                    st.markdown(f"**Scheduled Time:** {time_display} Central Time")
                    
                    # Car details
                    car_listing = visit.get('carListing', {})
                    if car_listing:
                        st.markdown("#### Car Information")
                        col_car1, col_car2 = st.columns(2)
                        
                        with col_car1:
                            st.markdown(f"**Year:** {car_listing.get('year', 'N/A')}")
                            st.markdown(f"**Make:** {car_listing.get('make', 'N/A')}")
                            st.markdown(f"**Model:** {car_listing.get('model', 'N/A')}")
                            st.markdown(f"**Miles:** {car_listing.get('miles', 'N/A'):,}" if car_listing.get('miles') else "**Miles:** N/A")
                        
                        with col_car2:
                            st.markdown(f"**Price:** ${car_listing.get('listingPrice', 'N/A'):,}" if car_listing.get('listingPrice') else "**Price:** N/A")
                            st.markdown(f"**Title Status:** {car_listing.get('titleStatus', 'N/A')}")
                            st.markdown(f"**Carfax:** {car_listing.get('carfaxDamageIncidents', 'N/A')}")
                            st.markdown(f"**Tires:** {'Yes' if car_listing.get('tireLifeLeft') else 'No' if car_listing.get('tireLifeLeft') is not None else 'N/A'}")
                        
                        if car_listing.get('docFeeQuoted'):
                            st.markdown(f"**Doc Fee Quoted:** ${car_listing.get('docFeeQuoted', 0):,}")
                        if car_listing.get('lowestPrice'):
                            st.markdown(f"**Lowest Price:** ${car_listing.get('lowestPrice', 0):,}")
                    else:
                        st.info("No car listing information available for this visit.")
                    
                    # Dealer info
                    thread = visit.get('thread', {})
                    if thread:
                        dealer_phone = thread.get('phoneNumber', 'N/A')
                        st.markdown(f"**Dealer Phone:** {format_phone_number(dealer_phone)}")
                    
                    # Notes
                    if visit.get('notes'):
                        st.markdown(f"**Notes:** {visit.get('notes')}")
                    
                    # Close button
                    if st.button("Close", key="close_visit_modal"):
                        del st.session_state.selected_visit
                        st.rerun()
        except Exception as e:
            st.error(f"Error loading visits: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        st.info("Connect to the API to view scheduled visits.")
    
elif page == "Listings":
    st.title("Car Listings")
    
    if not api_connected:
        st.error(f"⚠️ Cannot connect to backend API at {API_BASE_URL}. Please ensure the backend server is running.")
        st.stop()
    
    # Fetch listings
    listings = []
    valid_listings = []
    try:
        response = requests.get(f"{API_BASE_URL}/car-listings", timeout=5)
        if response.status_code == 200:
            listings = response.json()
            # Filter out listings without miles or listingPrice
            valid_listings = [l for l in listings if l.get('miles') is not None and l.get('listingPrice') is not None]
        elif response.status_code == 503:
            st.error("Database unavailable. Please check your MongoDB connection.")
        else:
            st.error(f"Failed to fetch car listings (Status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Connection refused. Is the backend running on port {API_PORT}?")
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timed out. The backend may be slow or unresponsive.")
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")
    
    if listings:
        # Show all listings in a table
        st.markdown("### All Listings")
        display_listings = []
        for listing in listings:
            display_listings.append({
                "Year": listing.get('year', 'N/A'),
                "Make": listing.get('make', 'N/A'),
                "Model": listing.get('model', 'N/A'),
                "Miles": f"{listing.get('miles', 0):,}" if listing.get('miles') else 'N/A',
                "Price": f"${listing.get('listingPrice', 0):,}" if listing.get('listingPrice') else 'N/A',
                "Phone": format_phone_number(listing.get('phoneNumber', 'N/A')),
                "Complete": "✅" if listing.get('conversationComplete') else "⏳"
            })
        
        if display_listings:
            st.dataframe(display_listings, use_container_width=True, hide_index=True)
        
        # Show scatter plot for valid listings
        if valid_listings:
            st.markdown("### Price vs Miles Visualization")
            import plotly.graph_objects as go
            
            x_data = [l.get('miles', 0) for l in valid_listings]
            y_data = [l.get('listingPrice', 0) for l in valid_listings]
            
            # Create hover text
            hover_texts = []
            for listing in valid_listings:
                miles = listing.get('miles')
                price = listing.get('listingPrice')
                doc_fee = listing.get('docFeeQuoted')
                lowest_price = listing.get('lowestPrice')
                
                hover_text = f"Make: {listing.get('make', 'N/A')}<br>"
                hover_text += f"Model: {listing.get('model', 'N/A')}<br>"
                hover_text += f"Year: {listing.get('year', 'N/A')}<br>"
                hover_text += f"Miles: {miles:,}<br>" if miles is not None else "Miles: N/A<br>"
                hover_text += f"Price: ${price:,}<br>" if price is not None else "Price: N/A<br>"
                hover_text += f"Tires: {'Yes' if listing.get('tireLifeLeft') else 'No' if listing.get('tireLifeLeft') is not None else 'N/A'}<br>"
                hover_text += f"Title: {listing.get('titleStatus', 'N/A')}<br>"
                hover_text += f"Carfax: {listing.get('carfaxDamageIncidents', 'N/A')}<br>"
                hover_text += f"Doc Fee: ${doc_fee:,}<br>" if doc_fee is not None else "Doc Fee: N/A<br>"
                hover_text += f"Lowest Price: ${lowest_price:,}<br>" if lowest_price is not None else "Lowest Price: N/A<br>"
                hover_text += f"Phone: {listing.get('phoneNumber', 'N/A')}"
                hover_texts.append(hover_text)
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                mode='markers',
                marker=dict(
                    size=12,
                    color='#007bff',
                    line=dict(width=2, color='#0056b3')
                ),
                text=hover_texts,
                hoverinfo='text',
                name='Cars'
            ))
            
            fig.update_layout(
                title="Car Listings: Price vs Miles",
                xaxis_title="Number of Miles",
                yaxis_title="Listing Price ($)",
                height=600,
                hovermode='closest',
                margin=dict(l=80, r=20, t=50, b=60),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    title_font=dict(color='#212529', size=14),
                    tickfont=dict(color='#212529', size=12),
                    showline=True,
                    linecolor='#212529',
                    linewidth=1
                ),
                yaxis=dict(
                    title_font=dict(color='#212529', size=14),
                    tickfont=dict(color='#212529', size=12),
                    showline=True,
                    linecolor='#212529',
                    linewidth=1
                ),
                title_font=dict(color='#212529')
            )
            
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No car listings yet. Complete conversations to see listings here.")
    
    # Auto-refresh button
    if st.button("Refresh"):
        st.rerun()
    
    # Auto-refresh every 10 seconds (commented out to avoid constant refreshing)
    # time.sleep(10)
    # st.rerun()

