#!/usr/bin/env python
"""Launch script for MarketPulse AI FastAPI backend.

This script starts the FastAPI backend server with auto-reload enabled.

Usage:
    python run_backend.py
"""

import subprocess
import sys

def main():
    """Launch the FastAPI backend."""
    print("=" * 60)
    print("MarketPulse AI Backend")
    print("=" * 60)
    print("\nStarting FastAPI server...")
    print("API will be available at: http://127.0.0.1:8000")
    print("Interactive docs at: http://127.0.0.1:8000/docs")
    print("\nPress Ctrl+C to stop the server.\n")
    print("=" * 60)
    
    try:
        subprocess.run([
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
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
