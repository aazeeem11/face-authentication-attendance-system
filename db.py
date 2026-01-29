"""
db.py - Database Operations Module

This module manages SQLite database operations for attendance tracking.

Database Schema:
- Table: attendance
  - id (INTEGER PRIMARY KEY)
  - name (TEXT)
  - date (TEXT)
  - punch_in (TEXT - timestamp)
  - punch_out (TEXT - timestamp)

Attendance Logic:
1. First face recognition of the day → Punch-In
2. Second face recognition of the day → Punch-Out
3. Multiple recognitions after punch-out → New punch-in (next day or shift)

Key Features:
- SQLite for lightweight, serverless storage
- Daily attendance tracking per user
- Timestamp recording for analysis
"""

import sqlite3
import pandas as pd
from datetime import datetime, date
import streamlit as st
import os


class AttendanceDB:
    """
    Manages attendance database operations using SQLite.
    """
    
    def __init__(self, db_path="database/attendance.db"):
        """
        Initialize database connection.
        
        Args:
            db_path (str): Path to SQLite database file
        """
        self.db_path = db_path
        
        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database schema
        self._init_database()
    
    def _init_database(self):
        """
        Create attendance table if it doesn't exist.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create attendance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    punch_in TEXT NOT NULL,
                    punch_out TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_name_date 
                ON attendance(name, date)
            ''')
            
            conn.commit()
            conn.close()
        
        except Exception as e:
            st.error(f"❌ Database initialization error: {str(e)}")


    
    def mark_attendance(self, name):
        """
        Mark attendance (punch-in or punch-out) for a user.
        
        Logic:
        1. Check if user has already punched in today
        2. If NO: Create new record with punch_in timestamp
        3. If YES: Update existing record with punch_out timestamp
        
        Args:
            name (str): User name
            
        Returns:
            dict: {
                'success': bool,
                'action': 'punch_in' or 'punch_out',
                'message': str,
                'timestamp': str
            }
        """
        try:
            today = date.today().strftime("%Y-%m-%d")
            current_time = datetime.now().strftime("%H:%M:%S")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if user has punched in today
            cursor.execute(
                '''
                SELECT id, punch_out FROM attendance 
                WHERE name = ? AND date = ? 
                ORDER BY id DESC LIMIT 1
                ''',
                (name, today)
            )
            
            record = cursor.fetchone()
            
            if record is None:
                # No record today → Punch-In
                cursor.execute(
                    '''
                    INSERT INTO attendance (name, date, punch_in, punch_out)
                    VALUES (?, ?, ?, NULL)
                    ''',
                    (name, today, current_time)
                )
                conn.commit()
                conn.close()
                
                return {
                    'success': True,
                    'action': 'punch_in',
                    'message': f'✅ Punch-In recorded for {name} at {current_time}',
                    'timestamp': current_time
                }
            
            elif record[1] is None:
                # Punched in but not out → Punch-Out
                cursor.execute(
                    '''
                    UPDATE attendance 
                    SET punch_out = ? 
                    WHERE id = ?
                    ''',
                    (current_time, record[0])
                )
                conn.commit()
                conn.close()
                
                return {
                    'success': True,
                    'action': 'punch_out',
                    'message': f'✅ Punch-Out recorded for {name} at {current_time}',
                    'timestamp': current_time
                }
            
            else:
                # Already punched out today
                conn.close()
                return {
                    'success': False,
                    'action': 'none',
                    'message': f'⚠️ {name} already marked attendance for today (Punch-Out: {record[1]})',
                    'timestamp': record[1]
                }
        
        except Exception as e:
            st.error(f"❌ Error marking attendance: {str(e)}")
            return {
                'success': False,
                'action': 'none',
                'message': f'❌ Error: {str(e)}',
                'timestamp': None
            }
    
    def get_today_attendance(self):
        """
        Get all attendance records for today.
        
        Returns:
            pd.DataFrame: DataFrame with columns [name, punch_in, punch_out, duration]
        """
        try:
            today = date.today().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(self.db_path)
            query = '''
                SELECT name, punch_in, punch_out, 
                       CASE 
                           WHEN punch_out IS NOT NULL 
                           THEN (julianday(punch_out) - julianday(punch_in)) * 24
                           ELSE NULL
                       END as hours_worked
                FROM attendance
                WHERE date = ?
                ORDER BY punch_in
            '''
            
            df = pd.read_sql_query(query, conn, params=(today,))
            conn.close()
            
            return df
        
        except Exception as e:
            st.error(f"❌ Error fetching today's attendance: {str(e)}")
            return pd.DataFrame()
    
    def get_monthly_attendance(self, year, month):
        """
        Get all attendance records for a specific month.
        
        Args:
            year (int): Year (e.g., 2024)
            month (int): Month (1-12)
            
        Returns:
            pd.DataFrame: Monthly attendance records
        """
        try:
            # Date range for the month
            start_date = f"{year:04d}-{month:02d}-01"
            
            # Calculate end date
            if month == 12:
                end_date = f"{year+1:04d}-01-01"
            else:
                end_date = f"{year:04d}-{month+1:02d}-01"
            
            conn = sqlite3.connect(self.db_path)
            query = '''
                SELECT name, date, punch_in, punch_out,
                       CASE 
                           WHEN punch_out IS NOT NULL 
                           THEN (julianday(punch_out) - julianday(punch_in)) * 24
                           ELSE NULL
                       END as hours_worked
                FROM attendance
                WHERE date >= ? AND date < ?
                ORDER BY date DESC, punch_in
            '''
            
            df = pd.read_sql_query(query, conn, params=(start_date, end_date))
            conn.close()
            
            return df
        
        except Exception as e:
            st.error(f"❌ Error fetching monthly attendance: {str(e)}")
            return pd.DataFrame()
    
    def get_user_attendance_summary(self, name, year, month):
        """
        Get attendance summary for a specific user in a month.
        
        Returns:
            dict: {
                'total_days_present': int,
                'total_hours': float,
                'days_with_punch_out': int,
                'incomplete_days': int
            }
        """
        try:
            df = self.get_monthly_attendance(year, month)
            
            if df.empty:
                return {
                    'total_days_present': 0,
                    'total_hours': 0.0,
                    'days_with_punch_out': 0,
                    'incomplete_days': 0
                }
            
            # Filter for specific user
            user_df = df[df['name'] == name]
            
            if user_df.empty:
                return {
                    'total_days_present': 0,
                    'total_hours': 0.0,
                    'days_with_punch_out': 0,
                    'incomplete_days': 0
                }
            
            total_days_present = len(user_df)
            days_with_punch_out = len(user_df[user_df['punch_out'].notna()])
            incomplete_days = total_days_present - days_with_punch_out
            total_hours = user_df['hours_worked'].sum() if 'hours_worked' in user_df.columns else 0
            
            return {
                'total_days_present': total_days_present,
                'total_hours': float(total_hours) if total_hours else 0.0,
                'days_with_punch_out': days_with_punch_out,
                'incomplete_days': incomplete_days
            }
        
        except Exception as e:
            st.error(f"❌ Error generating summary: {str(e)}")
            return {
                'total_days_present': 0,
                'total_hours': 0.0,
                'days_with_punch_out': 0,
                'incomplete_days': 0
            }
    
    def get_all_users(self):
        """
        Get list of all users who have marked attendance.
        
        Returns:
            list: List of unique user names
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT DISTINCT name FROM attendance ORDER BY name')
            users = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return users
        
        except Exception as e:
            st.error(f"❌ Error fetching users: {str(e)}")
            return []


def get_attendance_db():
    """
    Get or create attendance database (Streamlit session state).
    
    Returns:
        AttendanceDB: Initialized database instance
    """
    if 'attendance_db' not in st.session_state:
        st.session_state.attendance_db = AttendanceDB()
    
    return st.session_state.attendance_db
