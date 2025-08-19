import streamlit as st
import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="WheresMyJobAt | Auto Job Tracker", layout="wide", initial_sidebar_state="collapsed")

# Minimal CSS
st.markdown("""
<style>
.metric-card { background: #f0f2f6; padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0; }
.app-card { background: white; padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0; 
           border-left: 4px solid #4A90E2; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.loading-container { display: flex; flex-direction: column; align-items: center; justify-content: center; 
    padding: 3rem; text-align: center; background: #f8f9fa; border-radius: 10px; margin: 2rem 0; }
.spinner { border: 4px solid #f3f3f3; border-top: 4px solid #4A90E2; border-radius: 50%; 
    width: 40px; height: 40px; animation: spin 1s linear infinite; margin-bottom: 1rem; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.realtime-indicator { 
    position: fixed; top: 10px; right: 10px; z-index: 1000;
    background: #27AE60; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;
}
.realtime-indicator.disconnected { background: #E74C3C; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = 0
if 'post_auth_loading' not in st.session_state:
    st.session_state.post_auth_loading = False
if 'auth_loading_start' not in st.session_state:
    st.session_state.auth_loading_start = 0
if 'realtime_update_trigger' not in st.session_state:
    st.session_state.realtime_update_trigger = 0
if 'websocket_connected' not in st.session_state:
    st.session_state.websocket_connected = False
if 'last_hash' not in st.session_state:
    st.session_state.last_hash = ''

# Handle auth success
if st.query_params.get('auth') == 'success':
    st.query_params.clear()
    st.session_state.post_auth_loading = True
    st.session_state.auth_loading_start = time.time()
    st.rerun()

st.markdown("<h1 style='text-align: center; color: #4A90E2;'>WheresMyJobAt</h1><h3 style='text-align: center; color: #666;'>Auto Job Application Tracker</h3>", unsafe_allow_html=True)

# Add real-time WebSocket client
backend_url = f"{os.getenv('BACKEND_URL', 'http://localhost')}:{os.getenv('BACKEND_PORT', '5000')}"
websocket_js = f"""
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.js"></script>
<script>
let socket = null;
let isConnected = false;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

function updateIndicator(connected) {{
    const indicator = document.getElementById('realtime-indicator');
    if (indicator) {{
        indicator.textContent = connected ? '🟢 Real-time' : '🔴 Offline';
        indicator.className = connected ? 'realtime-indicator' : 'realtime-indicator disconnected';
    }}
}}

function triggerStreamlitRefresh() {{
    // Use a more streamlit-friendly approach
    const timestamp = Date.now();
    
    // Method 1: Update URL params to trigger Streamlit refresh
    const url = new URL(window.location);
    url.searchParams.set('refresh', timestamp);
    window.history.replaceState({{}}, '', url);
    
    // Method 2: Try to trigger Streamlit's internal refresh mechanism
    try {{
        // Look for Streamlit's refresh mechanism
        if (window.parent && window.parent.postMessage) {{
            window.parent.postMessage({{
                isStreamlitMessage: true,
                type: 'RERUN_SCRIPT'
            }}, '*');
        }}
        
        // Alternative: dispatch a custom event that Streamlit might listen to
        window.dispatchEvent(new CustomEvent('streamlit:refresh', {{
            detail: {{ timestamp: timestamp }}
        }}));
        
    }} catch (e) {{
        console.log('Streamlit refresh methods failed, using fallback');
        // Only use page reload as last resort after a longer delay
        setTimeout(() => {{
            window.location.reload();
        }}, 2000);
    }}
}}

function connectWebSocket() {{
    try {{
        socket = io('{backend_url}', {{
            transports: ['websocket', 'polling'],
            timeout: 10000,
            forceNew: true
        }});
        
        socket.on('connect', function() {{
            console.log('🔗 Connected to real-time updates!');
            console.log('Backend URL:', '{backend_url}');
            isConnected = true;
            reconnectAttempts = 0;
            updateIndicator(true);
            
            // Test the connection by sending a ping
            socket.emit('ping', {{ timestamp: Date.now() }});
        }});
        
        socket.on('disconnect', function() {{
            console.log('❌ Disconnected from real-time updates');
            isConnected = false;
            updateIndicator(false);
        }});
        
        socket.on('applications_updated', function(data) {{
            console.log('📊 Applications updated!', data);
            console.log('Total applications received:', Object.values(data).flat().length);
            
            // Show brief visual feedback for real-time update
            const indicator = document.getElementById('realtime-indicator');
            if (indicator) {{
                const originalText = indicator.textContent;
                indicator.textContent = '⚡ Updating...';
                indicator.style.background = '#F39C12';
                setTimeout(() => {{
                    indicator.textContent = originalText;
                    indicator.style.background = '#27AE60';
                }}, 1000);
            }}
            
            console.log('Triggering Streamlit refresh...');
            forceStreamlitRefresh();
        }});
        
        socket.on('new_application_detected', function(data) {{
            console.log('🎉 NEW APPLICATION DETECTED!', data);
            
            // Show special visual feedback for new applications
            const indicator = document.getElementById('realtime-indicator');
            if (indicator) {{
                indicator.textContent = '🎉 New App!';
                indicator.style.background = '#E74C3C';
                setTimeout(() => {{
                    indicator.textContent = '🟢 Real-time';
                    indicator.style.background = '#27AE60';
                }}, 3000);
            }}
            
            // Show notification
            if ('Notification' in window && Notification.permission === 'granted') {{
                new Notification('New Job Application Detected!', {{
                    body: `${{data.company}} - ${{data.position}} (${{data.stage}})`,
                    icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🎉</text></svg>'
                }});
            }}
            forceStreamlitRefresh();
        }});
        
        socket.on('connect_error', function(error) {{
            console.log('Connection error:', error);
            isConnected = false;
            updateIndicator(false);
            
            // Retry connection with exponential backoff
            if (reconnectAttempts < maxReconnectAttempts) {{
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                console.log(`Retrying connection in ${{delay}}ms... (attempt ${{reconnectAttempts}})`);
                setTimeout(connectWebSocket, delay);
            }}
        }});
        
    }} catch (error) {{
        console.error('Failed to connect WebSocket:', error);
        updateIndicator(false);
    }}
}}

// Request notification permission
if ('Notification' in window && Notification.permission === 'default') {{
    Notification.requestPermission();
}}

// Connect when page loads
if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', connectWebSocket);
}} else {{
    connectWebSocket();
}}

// Reconnect when window becomes visible again
document.addEventListener('visibilitychange', function() {{
    if (!document.hidden && !isConnected) {{
        console.log('Page became visible, attempting to reconnect...');
        connectWebSocket();
    }}
}});

// Simplified approach for better reliability
console.log('WebSocket client initialized for backend:', '{backend_url}');
</script>
<div id="realtime-indicator" class="realtime-indicator disconnected">🔴 Connecting...</div>
"""

st.markdown(websocket_js, unsafe_allow_html=True)

# API helper
def api(endpoint, method='GET', data=None):
    try:
        response = getattr(requests, method.lower())(f"{os.getenv("BACKEND_URL", "http://localhost")}:{os.getenv("BACKEND_PORT", "5000")}{endpoint}", json=data)
        return response.status_code == 200, response.json() if response.content else None
    except:
        return False, None

# Get data
monitor_ok, monitor = api("/api/monitor/status")
apps_ok, apps = api("/api/applications")
if not apps_ok:
    st.error("⚠️ Backend not running. Start server: `cd server && python app.py`")
    apps = {"Applied": [], "Interview": [], "Offer": [], "Rejected": []}
monitoring = monitor_ok and monitor and monitor.get('is_running', False)

# Show sign-in page if not authenticated
if not monitoring and not st.session_state.post_auth_loading:
    if st.button("🔐 Connect with Google", key="google_signin"):
        ok, auth = api("/api/gmail/auth-url")
        if ok and auth:
            st.markdown(f'<meta http-equiv="refresh" content="0; url={auth["auth_url"]}" />', unsafe_allow_html=True)
        else:
            st.error("❌ Failed to get authorization URL")
    
    # Apply custom styling to the sign-in button
    st.markdown("""
        <style>
        div[data-testid="stButton"] > button[kind="secondary"] {
            background-color: #357ae8 !important;
            color: white !important;
            width: 400px !important;
            font-size: 30px !important;
            font-weight: bold !important;
            padding: 12px 24px !important;
            border-radius: 8px !important;
            border: none !important;
            margin: 0 auto !important;
            margin-top: 100px !important;
            display: block !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.stop()

# Handle post-auth loading
if st.session_state.post_auth_loading:
    total_apps = sum(len(stage_apps) for stage_apps in apps.values())
    if monitoring and total_apps > 0:
        st.session_state.post_auth_loading = False
        st.rerun()
    elif time.time() - st.session_state.auth_loading_start > 30:
        st.session_state.post_auth_loading = False
        st.error("⚠️ Authentication completed but setup is taking longer than expected. Try refreshing.")
        st.rerun()
    else:
        st.markdown("""
            <div class="loading-container">
                <div class="spinner"></div>
                <h3 style="color: #4A90E2; margin: 0;">Setting up your job tracker...</h3>
                <p style="color: #666; margin: 0.5rem 0;">
                    ✅ Gmail connected successfully<br>🔄 Loading applications and starting monitoring...
                </p>
            </div>
        """, unsafe_allow_html=True)
        time.sleep(2)
        st.rerun()

# Sidebar
with st.sidebar:
    st.markdown("### 📧 Gmail Connection")
    
    if monitoring:
        st.success(f"✅ {monitor.get('gmail_email', 'Gmail')} Connected")
        if st.button("🛑 Stop Monitoring", use_container_width=True):
            api("/api/monitor/stop", "POST")
            st.rerun()
    
    st.markdown("➕ Manually Add Application")
    with st.form("add_app"):
        company = st.text_input("Company Name")
        position = st.text_input("Position")
        stage = st.selectbox("Stage", ["Applied", "Interview", "Offer", "Rejected"])
        
        if st.form_submit_button("Add Application", use_container_width=True):
            if company and position:
                if api("/api/applications", "POST", {"company": company, "position": position, "stage": stage})[0]:
                    st.success("✅ Application added! Real-time update sent.")
                    # Trigger immediate refresh for manual additions
                    st.session_state.last_refresh = 0  # Force immediate refresh
                    time.sleep(0.5)  # Shorter delay for better UX
                    st.rerun()
                else:
                    st.error("❌ Failed to add application")
            else:
                st.error("Please fill in both company and position")

# Enhanced auto-refresh with real-time WebSocket integration
current_time = time.time()

# Check for hash-based refresh trigger (from JavaScript WebSocket client)
current_hash = st.query_params.get('refresh', '')
if current_hash and current_hash != st.session_state.get('last_hash', ''):
    st.session_state.last_hash = current_hash
    st.session_state.last_refresh = current_time
    st.query_params.clear()  # Clear the refresh trigger
    st.rerun()

# Alternative refresh mechanism - check for special session state trigger
if st.session_state.get('websocket_refresh_trigger', 0) != st.session_state.get('last_websocket_refresh', 0):
    st.session_state.last_websocket_refresh = st.session_state.get('websocket_refresh_trigger', 0)
    st.session_state.last_refresh = current_time
    st.rerun()

# Faster polling when monitoring is active (every 3 seconds instead of 10)
refresh_interval = 3 if monitoring else 10
if not st.session_state.post_auth_loading and current_time - st.session_state.last_refresh > refresh_interval:
    st.session_state.last_refresh = current_time
    st.rerun()

# Add a more robust refresh component
refresh_component = f"""
<script>
let refreshCounter = 0;

// Function to trigger Streamlit refresh using multiple methods
function forceStreamlitRefresh() {{
    refreshCounter++;
    console.log(`Attempting Streamlit refresh #${{refreshCounter}}`);
    
    // Method 1: Update URL params
    const url = new URL(window.location);
    url.searchParams.set('refresh', Date.now());
    window.history.replaceState({{}}, '', url);
    
    // Method 2: Try to access Streamlit's internal state (if available)
    try {{
        if (window.streamlitDebug) {{
            window.streamlitDebug.forceRerun();
        }}
    }} catch (e) {{
        console.log('Streamlit debug method not available');
    }}
    
    // Method 3: Set a flag in localStorage that we check for
    localStorage.setItem('streamlit_refresh_needed', Date.now());
    
    // Method 4: As last resort, reload page but only after other methods have had time
    setTimeout(() => {{
        console.log('Using page reload as final fallback');
        window.location.reload();
    }}, 3000);
}}

// Check localStorage for refresh flags
setInterval(() => {{
    const refreshFlag = localStorage.getItem('streamlit_refresh_needed');
    if (refreshFlag) {{
        const refreshTime = parseInt(refreshFlag);
        const now = Date.now();
        
        // If refresh flag is recent (within 5 seconds), trigger refresh
        if (now - refreshTime < 5000) {{
            localStorage.removeItem('streamlit_refresh_needed');
            
            // Add to URL params to trigger Streamlit refresh
            const url = new URL(window.location);
            url.searchParams.set('refresh', refreshTime);
            window.history.replaceState({{}}, '', url);
        }}
    }}
}}, 100);

// Check for URL hash changes to trigger refresh
let lastHash = window.location.hash;
setInterval(function() {{
    if (window.location.hash !== lastHash) {{
        lastHash = window.location.hash;
        if (lastHash.includes('refresh-')) {{
            // Extract timestamp and trigger Streamlit rerun
            const timestamp = lastHash.split('refresh-')[1];
            if (timestamp && !isNaN(timestamp)) {{
                forceStreamlitRefresh();
            }}
        }}
    }}
}}, 200);
</script>
"""
st.markdown(refresh_component, unsafe_allow_html=True)

stages = ["Applied", "Interview", "Offer", "Rejected"]
colors = ["#4A90E2", "#F39C12", "#27AE60", "#E74C3C"]
emojis = ["📄", "🎤", "🎉", "❌"]

# Metrics
cols = st.columns(4)
for i, (stage, color, emoji) in enumerate(zip(stages, colors, emojis)):
    with cols[i]:
        st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid {color};">
                <h3 style="margin:0; color:{color};">{emoji} {stage}</h3>
                <h2 style="margin:0; color:{color};">{len(apps.get(stage, []))}</h2>
            </div>
        """, unsafe_allow_html=True)

# Applications
st.markdown("### 📋 Your Applications")
cols = st.columns(4)

for i, stage in enumerate(stages):
    with cols[i]:
        st.markdown(f"#### {emojis[i]} {stage}")
        
        for app in apps.get(stage, []):
            color = colors[i]
            st.markdown(f"""
                <div class="app-card" style="border-left-color: {color};">
                    <strong style="color: {color};">{app['company']}</strong><br>
                    <em style="color: {color};">{app['position']}</em><br>
                    <small style="color: {color};">Added: {app['date_added']}</small>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                new_stage = st.selectbox("Move to:", stages, key=f"m{app['id']}", label_visibility="collapsed", index=stages.index(stage))
                if st.button("Move", key=f"bm{app['id']}", use_container_width=True):
                    if api(f"/api/applications/{app['id']}", "PUT", {"stage": new_stage})[0]:
                        st.success(f"Moved to {new_stage}! Real-time update sent.")
                        st.session_state.last_refresh = 0  # Force immediate refresh
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Failed")
            
            with col2:
                if st.button("🗑️", key=f"bd{app['id']}", use_container_width=True):
                    if api(f"/api/applications/{app['id']}", "DELETE")[0]:
                        st.success("Deleted! Real-time update sent.")
                        st.session_state.last_refresh = 0  # Force immediate refresh
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Failed")

# Empty state
if sum(len(apps.get(stage, [])) for stage in stages) == 0:
    st.markdown("""
        <div style="text-align: center; padding: 2rem; color: #666;">
            <h3>No applications yet!</h3>
            <p>Connect your Gmail to start automatic tracking, or add applications manually.</p>
        </div>
    """, unsafe_allow_html=True)
