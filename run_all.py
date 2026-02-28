#!/usr/bin/env python
import os
from pathlib import Path
"""Launch script to run the backend API.

Usage:
    python run_all.py
"""

import subprocess
import sys
import time

def main():
    """Launch the FastAPI backend."""
    print("=" * 60)
    print("MarketPulse AI - Backend Service Launch")
    print("=" * 60)
    print("\nStarting the API Service...")
    print("Backend: http://127.0.0.1:8000")
    print("\nPress Ctrl+C to stop the service.\n")
    print("=" * 60)
    
    backend_process = None
    
    try:
        print("\nStarting FastAPI backend...")
        import os
        env = os.environ.copy()
        # Add src to PYTHONPATH so marketpulse module can be found
        src_path = str(Path(__file__).parent / "src")
        env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
        
        backend_process = subprocess.Popen([
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
        
        print("\n" + "=" * 60)
        print("✅ Backend service is running!")
        print("=" * 60)
        print("\nBackend API: http://127.0.0.1:8000")
        print("API Docs: http://127.0.0.1:8000/docs")
        print("React Frontend: Use 'npm run dev' inside the frontend/ directory.")
        print("\nPress Ctrl+C to stop the API.")
        print("=" * 60 + "\n")
        
        backend_process.wait()
        
    except KeyboardInterrupt:
        print("\n\nStopping API service...")
        if backend_process:
            backend_process.terminate()
        print("Service stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()

