#!/usr/bin/env python
"""Launch script for MarketPulse AI Streamlit dashboard.

This script starts the Streamlit dashboard which connects to the FastAPI backend.
Make sure the FastAPI server is running before launching the dashboard.

Usage:
    python run_dashboard.py
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Launch the Streamlit dashboard."""
    dashboard_path = Path(__file__).parent / "app" / "dashboard" / "app.py"
    
    if not dashboard_path.exists():
        print(f"Error: Dashboard file not found at {dashboard_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("MarketPulse AI Dashboard")
    print("=" * 60)
    print("\nStarting Streamlit dashboard...")
    print("Make sure the FastAPI backend is running at http://127.0.0.1:8000")
    print("\nDashboard will open in your browser automatically.")
    print("Press Ctrl+C to stop the dashboard.\n")
    print("=" * 60)
    
    try:
        subprocess.run([
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_path),
            "--server.port=8501",
            "--server.address=localhost"
        ])
    except KeyboardInterrupt:
        print("\n\nDashboard stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
