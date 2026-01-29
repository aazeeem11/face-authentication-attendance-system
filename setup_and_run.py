#!/usr/bin/env python3
"""
setup_and_run.py - One-click setup and run script

This script automates:
1. Virtual environment activation
2. Dependency installation
3. Directory creation
4. Application startup
"""

import os
import sys
import subprocess
import platform

def run_command(cmd, description):
    """Execute a command and report status."""
    print(f"\n📍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True)
        print(f"✅ {description} - Success!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Failed!")
        print(f"Error: {str(e)}")
        return False

def main():
    """Main setup routine."""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║  Face Authentication Attendance System - Setup & Run         ║
    ║  Production-Ready Face Recognition Attendance Tracking       ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Detect OS
    os_type = platform.system()
    print(f"🖥️  Detected OS: {os_type}")
    
    # Step 1: Check Python version
    print(f"\n🐍 Python Version: {sys.version}")
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required!")
        sys.exit(1)
    
    # Step 2: Virtual environment setup
    venv_path = "venv"
    if not os.path.exists(venv_path):
        if not run_command(f"{sys.executable} -m venv {venv_path}", "Creating virtual environment"):
            sys.exit(1)
    else:
        print(f"✅ Virtual environment already exists")
    
    # Step 3: Determine activation command
    if os_type == "Windows":
        activate_cmd = f".\\{venv_path}\\Scripts\\activate.bat"
        pip_cmd = f".\\{venv_path}\\Scripts\\pip"
        python_cmd = f".\\{venv_path}\\Scripts\\python"
    else:
        activate_cmd = f"source {venv_path}/bin/activate"
        pip_cmd = f"{venv_path}/bin/pip"
        python_cmd = f"{venv_path}/bin/python"
    
    # Step 4: Upgrade pip
    if not run_command(f"{pip_cmd} install --upgrade pip setuptools wheel", "Upgrading pip"):
        print("⚠️  Continuing despite pip upgrade issue...")
    
    # Step 5: Install requirements
    if not run_command(f"{pip_cmd} install -r requirements.txt", "Installing dependencies"):
        print("❌ Failed to install requirements!")
        sys.exit(1)
    
    # Step 6: Create data directories if needed
    print("\n📁 Creating data directories...")
    os.makedirs("data", exist_ok=True)
    os.makedirs("database", exist_ok=True)
    print("✅ Directories ready")
    
    # Step 7: Start application
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║  ✅ All setup complete! Starting application...             ║
    ║                                                               ║
    ║  💻 Open your browser to: http://localhost:8501              ║
    ║  📹 Allow camera access when prompted                        ║
    ║  🎯 Start by registering your face!                          ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Run Streamlit app
    os.system(f"{python_cmd} -m streamlit run app.py")

if __name__ == "__main__":
    main()
