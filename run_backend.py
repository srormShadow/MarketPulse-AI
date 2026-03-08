#!/usr/bin/env python
"""Launch script for MarketPulse AI FastAPI backend.

This script starts the FastAPI backend server with auto-reload enabled.

Usage:
    python run_backend.py

Note: If using Docker for DynamoDB/LocalStack, DynamoDB Local uses port 8000.
Run the backend in Docker too (port 8001), or stop the DynamoDB container
before running this script locally on port 8000.
"""

import subprocess
import sys
import os
from pathlib import Path

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
        env = os.environ.copy()
        # Add src to PYTHONPATH so marketpulse module can be found
        src_path = str(Path(__file__).parent / "src")
        env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
        
        subprocess.run([
            sys.executable,
            "-m",
            "uvicorn",
            "marketpulse.main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ], env=env)
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
