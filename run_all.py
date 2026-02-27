#!/usr/bin/env python
"""Launch script to run both backend and dashboard simultaneously.

This script starts both the FastAPI backend and Streamlit dashboard
in separate processes.

Usage:
    python run_all.py
"""

import subprocess
import sys
import time
from pathlib import Path

def main():
    """Launch both backend and dashboard."""
    print("=" * 60)
    print("MarketPulse AI - Full Stack Launch")
    print("=" * 60)
    print("\nStarting both backend and dashboard...")
    print("\nBackend: http://127.0.0.1:8000")
    print("Dashboard: http://localhost:8501")
    print("\nPress Ctrl+C to stop both services.\n")
    print("=" * 60)
    
    backend_process = None
    dashboard_process = None
    
    try:
        # Start backend
        print("\n[1/2] Starting FastAPI backend...")
        backend_process = subprocess.Popen([
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ])
        
        # Wait for backend to start
        print("Waiting for backend to initialize...")
        time.sleep(3)
        
        # Start dashboard
        print("\n[2/2] Starting Streamlit dashboard...")
        dashboard_path = Path(__file__).parent / "app" / "dashboard" / "app.py"
        dashboard_process = subprocess.Popen([
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_path),
            "--server.port=8501",
            "--server.address=localhost"
        ])
        
        print("\n" + "=" * 60)
        print("✅ Both services are running!")
        print("=" * 60)
        print("\nBackend API: http://127.0.0.1:8000")
        print("API Docs: http://127.0.0.1:8000/docs")
        print("Dashboard: http://localhost:8501")
        print("\nPress Ctrl+C to stop all services.")
        print("=" * 60 + "\n")
        
        # Wait for processes
        backend_process.wait()
        
    except KeyboardInterrupt:
        print("\n\nStopping all services...")
        if backend_process:
            backend_process.terminate()
        if dashboard_process:
            dashboard_process.terminate()
        print("All services stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
