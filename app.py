"""
app.py - Main Streamlit Application

Face Authentication Attendance System
A production-ready system for marking attendance using face recognition.

Features:
- Real-time face registration with validation
- Face-based authentication and user identification
- Attendance tracking with punch-in/punch-out
- Daily and monthly attendance reports
- Basic liveness detection for spoof prevention
- SQLite persistent database

Architecture:
┌─────────────────────────────────────────────────────┐
│                  Streamlit UI                       │
│  (Navigation: Register, Mark Attendance, Reports)   │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴───────────┬──────────────┬──────────────┐
        │                      │              │              │
    camera.py            face_utils.py      spoof.py        db.py
  (OpenCV frames)    (Face embeddings)   (Liveness)    (Attendance DB)
        │                      │              │              │
        └──────────────────────┴──────────────┴──────────────┘
                            Data Flow
"""

import streamlit as st
import cv2
import numpy as np
from datetime import datetime, date
import pandas as pd

# Import custom modules
from camera import get_camera
from face_utils import get_recognition_engine
from spoof import get_liveness_detector
from db import get_attendance_db


# ============================================================================
# STREAMLIT PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Face Authentication Attendance",
    page_icon="👤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stTitle {
        color: #1f77b4;
        text-align: center;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'camera_active' not in st.session_state:
        st.session_state.camera_active = False
    if 'capture_image' not in st.session_state:
        st.session_state.capture_image = None


def convert_cv2_to_rgb(frame):
    """Convert OpenCV BGR frame to RGB for display."""
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


# ============================================================================
# PAGE: REGISTER FACE
# ============================================================================

def page_register_face(camera_index=0):
    """Register a new user's face or add a new scan to an existing user."""
    st.header("👤 Register or Update Face")
    st.write("Register a new face or add more scans for an existing user to improve accuracy.")
    st.info("💡 You can add multiple images for the same user from different angles and in different lighting conditions.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Camera Feed")
        camera_placeholder = st.empty()
    
    with col2:
        st.subheader("Registration Settings")
        
        # Get existing users for the select box
        engine = get_recognition_engine()
        existing_users = engine.get_registered_users()
        
        # Let the user choose between a new user or an existing one
        registration_type = st.radio(
            "Registration Type",
            ["New User", "Existing User"],
            horizontal=True,
        )

        if registration_type == "New User":
            user_name = st.text_input(
                "Enter your name:",
                key="register_name",
                placeholder="e.g., John Doe"
            )
        else:
            if not existing_users:
                st.warning("No existing users found. Please register a new user first.")
                user_name = None
            else:
                user_name = st.selectbox(
                    "Select user to update:",
                    options=sorted(existing_users),
                    key="update_name"
                )

        liveness_check_button = st.button(
            "👁️ Start Liveness Check",
            key="liveness_check",
            disabled=(not user_name)
        )
        
        register_button = st.button(
            "✅ Register Face",
            key="register_submit",
            disabled=not st.session_state.get('frame_captured', False)
        )
    
    # Get camera and liveness detector
    camera = get_camera(camera_index)
    detector = get_liveness_detector()

    # Open camera if needed
    if not camera.cap:
        if not camera.open_camera():
            st.error("❌ Cannot access camera. Please check permissions.")
            return

    if liveness_check_button:
        st.session_state.liveness_check_started = True
        detector.reset()

    if st.session_state.get('liveness_check_started', False):
        st.info("Please blink your eyes to complete the liveness check.")
        
        # Liveness check loop
        for i in range(30): # Timeout after 30 frames
            frame_rgb, success = camera.capture_frame()
            if not success:
                st.error("❌ Failed to capture frame.")
                break
            
            camera_placeholder.image(frame_rgb, channels="RGB")
            liveness_result = detector.check_liveness(frame_rgb)

            if liveness_result['is_live']:
                st.session_state.captured_frame = frame_rgb
                st.session_state.frame_captured = True
                st.session_state.liveness_check_started = False
                st.success("✅ Liveness check successful! Frame captured.")
                st.experimental_rerun()
                break
        else:
            st.session_state.liveness_check_started = False
            st.error("❌ Liveness check failed. Please try again.")

    elif 'captured_frame' in st.session_state and st.session_state.get('frame_captured'):
        camera_placeholder.image(st.session_state.captured_frame, channels="RGB")
        st.info(f"📹 Captured frame resolution: {st.session_state.captured_frame.shape[1]}x{st.session_state.captured_frame.shape[0]}")
    else:
        # Show live feed
        frame_rgb, success = camera.capture_frame()
        if success:
            camera_placeholder.image(frame_rgb, channels="RGB")
        else:
            st.warning("⚠️ Unable to access camera feed")

    if register_button and user_name and 'captured_frame' in st.session_state:
        with st.spinner("🔄 Processing face..."):
            frame_rgb = st.session_state.captured_frame
            
            # Register face
            result = engine.register_face(frame_rgb, user_name)
            
            if result['success']:
                st.success(result['message'])
                st.balloons()
                st.session_state.captured_frame = None
                st.session_state.frame_captured = False
                
                # Show stats
                st.metric("Total Registered Users", engine.get_user_count())
                st.metric(f"Encodings for {user_name}", engine.get_user_encoding_count(user_name))
            else:
                st.error(result['message'])


# ============================================================================
# PAGE: MARK ATTENDANCE
# ============================================================================

def page_mark_attendance(camera_index=0):
    """Mark attendance through face recognition."""
    st.header("📝 Mark Attendance")
    st.write("Show your face to mark attendance (punch-in/punch-out).")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Camera Feed")
        camera_placeholder = st.empty()
    
    with col2:
        st.subheader("Recognition Result")
        result_placeholder = st.empty()
        confidence_placeholder = st.empty()
        attendance_placeholder = st.empty()
    
    # Get camera, recognition engine, and database
    camera = get_camera(camera_index)
    engine = get_recognition_engine()
    db = get_attendance_db()
    detector = get_liveness_detector()
    
    # Check if any users are registered
    if engine.get_user_count() == 0:
        st.warning("⚠️ No registered faces found. Please register faces first.")
        st.info("👉 Go to 'Register Face' tab to register users.")
        return
    
    # Open camera if needed
    if not camera.cap:
        if not camera.open_camera():
            st.error("❌ Cannot access camera. Please check permissions.")
            return
    
    # Try to recognize face
    frame_rgb, success = camera.capture_frame()
    
    if success:
        # Display frame
        camera_placeholder.image(frame_rgb, channels="RGB")
        
        # Try to recognize face
        recognition_result = engine.recognize_face(frame_rgb)
        
        # Display recognition result
        if recognition_result['success']:
            result_placeholder.success(f"✅ Recognized: **{recognition_result['name']}**")
            confidence = recognition_result['confidence']
            confidence_placeholder.metric("Confidence", f"{confidence:.1%}")
            
            # Mark attendance
            attendance_result = db.mark_attendance(recognition_result['name'])
            
            if attendance_result['success']:
                action = attendance_result['action'].replace('_', ' ').title()
                attendance_placeholder.success(f"✅ {action}: {attendance_result['timestamp']}")
                st.balloons()
            else:
                attendance_placeholder.warning(attendance_result['message'])
        else:
            result_placeholder.warning(f"⚠️ {recognition_result['message']}")
            confidence_placeholder.metric("Confidence", "0.0%")
    else:
        st.error("❌ Failed to capture frame.")


# ============================================================================
# PAGE: VIEW ATTENDANCE RECORDS
# ============================================================================

def page_view_attendance():
    """View attendance records."""
    st.header("📊 Attendance Records")
    
    tab1, tab2, tab3 = st.tabs(["📅 Today", "📈 Monthly", "👤 User Summary"])
    
    db = get_attendance_db()
    
    # Tab 1: Today's Attendance
    with tab1:
        st.subheader("Today's Attendance")
        
        today_df = db.get_today_attendance()
        
        if today_df.empty:
            st.info("ℹ️ No attendance records for today.")
        else:
            # Display as table
            st.dataframe(
                today_df.style.format({
                    'hours_worked': '{:.2f}'
                })
            )
            
            # Show statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Attendees", len(today_df))
            
            with col2:
                punched_out = len(today_df[today_df['punch_out'].notna()])
                st.metric("Punched Out", punched_out)
            
            with col3:
                still_present = len(today_df[today_df['punch_out'].isna()])
                st.metric("Still Present", still_present)
            
            with col4:
                if 'hours_worked' in today_df.columns:
                    avg_hours = today_df['hours_worked'].mean()
                    st.metric("Avg Hours", f"{avg_hours:.2f}" if avg_hours else "—")
    
    # Tab 2: Monthly Attendance
    with tab2:
        st.subheader("Monthly Attendance Report")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_month = st.date_input(
                "Select month:",
                value=date.today(),
                format="YYYY-MM-DD"
            )
        
        with col2:
            st.empty()  # For alignment
        
        month_df = db.get_monthly_attendance(
            selected_month.year,
            selected_month.month
        )
        
        if month_df.empty:
            st.info("ℹ️ No attendance records for this month.")
        else:
            st.dataframe(
                month_df.style.format({
                    'hours_worked': '{:.2f}'
                })
            )
            
            # Show monthly statistics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Records", len(month_df))
            
            with col2:
                unique_users = month_df['name'].nunique()
                st.metric("Unique Users", unique_users)
            
            with col3:
                total_hours = month_df['hours_worked'].sum() if 'hours_worked' in month_df.columns else 0
                st.metric("Total Hours", f"{total_hours:.1f}" if total_hours else "—")
    
    # Tab 3: User Summary
    with tab3:
        st.subheader("User Attendance Summary")
        
        users = db.get_all_users()
        
        if not users:
            st.info("ℹ️ No users have marked attendance yet.")
        else:
            selected_user = st.selectbox("Select user:", users)
            selected_month = st.date_input(
                "Select month:",
                value=date.today(),
                format="YYYY-MM-DD"
            )
            
            summary = db.get_user_attendance_summary(
                selected_user,
                selected_month.year,
                selected_month.month
            )
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Days Present", summary['total_days_present'])
            
            with col2:
                st.metric("Punched Out", summary['days_with_punch_out'])
            
            with col3:
                st.metric("Incomplete Days", summary['incomplete_days'])
            
            with col4:
                st.metric("Total Hours", f"{summary['total_hours']:.1f}")


# ============================================================================
# PAGE: SYSTEM INFO & SETTINGS
# ============================================================================

def page_system_info():
    """Display system information and allow user management."""
    st.header("⚙️ System Information & User Management")
    
    engine = get_recognition_engine()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 System Status")
        
        db = get_attendance_db()
        
        total_encodings = sum(len(encs) for encs in engine.known_faces.values())
        
        stats = {
            "Registered Users": engine.get_user_count(),
            "Total Face Encodings": total_encodings,
            "Attendance Records": len(db.get_all_users()),
        }
        
        for stat, value in stats.items():
            st.metric(stat, value)
    
    with col2:
        st.subheader("👥 Registered Users")
        
        users = engine.get_registered_users()
        
        if users:
            for user in sorted(users):
                enc_count = engine.get_user_encoding_count(user)
                user_col, count_col, button_col = st.columns([2, 1, 1])
                with user_col:
                    st.write(f"👤 **{user}**")
                with count_col:
                    st.write(f"({enc_count} scans)")
                with button_col:
                    if st.button(f"🗑️ Delete {user}", key=f"delete_{user}"):
                        with st.spinner(f"Deleting {user}..."):
                            delete_result = engine.delete_user(user)
                            if delete_result['success']:
                                st.success(delete_result['message'])
                                st.experimental_rerun()
                            else:
                                st.error(delete_result['message'])
        else:
            st.info("No users registered yet.")
    
    # Technical details
    st.subheader("🔧 Technical Details")
    
    tech_info = {
        "Face Recognition Library": "face_recognition (dlib + ResNet)",
        "Face Encoding Dimensions": "128-D vectors",
        "Distance Metric": "Euclidean distance",
        "Recognition Tolerance": f"{engine.tolerance}",
        "Database": "SQLite",
        "UI Framework": "Streamlit",
    }
    
    for tech, detail in tech_info.items():
        st.write(f"**{tech}:** {detail}")
    
    # Advanced settings
    st.subheader("⚡ Advanced Settings")
    
    new_tolerance = st.slider(
        "Face Recognition Tolerance (lower = stricter):",
        min_value=0.1,
        max_value=1.0,
        value=engine.tolerance,
        step=0.05,
        help="Adjust sensitivity for face matching"
    )
    
    if new_tolerance != engine.tolerance:
        engine.tolerance = new_tolerance
        st.success(f"✅ Tolerance updated to {new_tolerance}")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application logic."""
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar navigation
    st.sidebar.title("📍 Navigation")
    
    pages = {
        "🏠 Home": "home",
        "👤 Register Face": "register",
        "📝 Mark Attendance": "mark",
        "📊 View Records": "records",
        "⚙️ System Info": "settings",
    }
    
    selected_page = st.sidebar.radio("Select page:", list(pages.keys()))
    page_key = pages[selected_page]
    
    # Add camera selection in the sidebar
    st.sidebar.markdown("---")
    camera_index = st.sidebar.number_input("📷 Select Camera", min_value=0, max_value=10, value=0)
    
    # Sidebar info
    st.sidebar.markdown("---")
    st.sidebar.subheader("ℹ️ About")
    st.sidebar.info(
        "**Face Authentication Attendance System**\n\n"
        "A production-ready attendance system using face recognition.\n\n"
        "🔐 **Features:**\n"
        "- Face registration\n"
        "- Real-time recognition\n"
        "- Attendance tracking\n"
        "- Spoof detection\n"
    )
    
    # Page routing
    if page_key == "home":
        st.title("👤 Face Authentication Attendance System")
        
        st.markdown("""
        ## Welcome! 👋
        
        This is a **face authentication attendance system** 
        built with Python, OpenCV, and deep learning.
        
        ### 🚀 Quick Start
        
        1. **Register Your Face** - Go to the "Register Face" tab and capture your image
        2. **Mark Attendance** - Use "Mark Attendance" to punch-in/out with your face
        3. **View Records** - Check attendance history in "View Records"
        
        ### ✨ Key Features
        
        - ✅ **Real-time Face Recognition** - Instant identification using 128-D embeddings
        - 🔐 **Secure Storage** - SQLite database with encrypted storage
        - 📊 **Attendance Tracking** - Punch-in/out with timestamps
        - 🛡️ **Spoof Prevention** - Basic liveness detection to prevent photo spoofing
        - 📱 **Easy-to-Use UI** - Streamlit-based intuitive interface
        
        ### 🎯 How It Works
        
        **Face Registration:**
        - Camera captures your face
        - Face is detected and converted to a 128-D vector (embedding)
        - Embedding is stored in the database
        
        **Face Recognition:**
        - Your face is converted to an embedding
        - Compared with all registered embeddings
        - If distance < tolerance, you're identified!
        
        ### 📝 System Details
        """)
        
        engine = get_recognition_engine()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Registered Users", engine.get_user_count())
        
        with col2:
            st.metric("Total Encodings", sum(len(encs) for encs in engine.known_faces.values()))
        
        with col3:
            st.metric("Recognition Tolerance", f"{engine.tolerance}")
        
        st.markdown("""
        ---
        
        
        ---
        
        **Ready to get started?** Use the navigation menu on the left! 👈
        """)
    
    elif page_key == "register":
        page_register_face(camera_index)
    
    elif page_key == "mark":
        page_mark_attendance(camera_index)
    
    elif page_key == "records":
        page_view_attendance()
    
    elif page_key == "settings":
        page_system_info()


if __name__ == "__main__":
    main()
