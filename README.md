# MarketPulse AI Backend

Clean FastAPI backend foundation for MarketPulse AI with modular architecture, SQLite via SQLAlchemy, environment-based config, and logging.

## Project Structure

```text
MarketPulse-AI/
|-- app/
|   |-- api/
|   |   |-- v1/
|   |   |   |-- health.py
|   |   |   `-- __init__.py
|   |   |-- router.py
|   |   `-- __init__.py
|   |-- core/
|   |   |-- config.py
|   |   |-- logging.py
|   |   `-- __init__.py
|   |-- db/
|   |   |-- base.py
|   |   |-- init_db.py
|   |   |-- session.py
|   |   `-- __init__.py
|   |-- models/
|   |   |-- health_ping.py
|   |   `-- __init__.py
|   |-- main.py
|   `-- __init__.py
|-- .env.example
|-- requirements.txt
`-- README.md
```

## Features

- FastAPI application entrypoint (`app/main.py`)
- SQLite + SQLAlchemy engine/session setup
- Environment config via `pydantic-settings` and `.env`
- Centralized logging configuration
- Health check endpoint at `GET /health`

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy environment template:
   ```bash
   cp .env.example .env
   ```
4. Run the API:
   ```bash
   uvicorn app.main:app --reload
   ```

Open `http://127.0.0.1:8000/health`.
