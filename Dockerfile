FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src ./src
COPY data ./data
COPY .env.example ./.env.example

USER app

EXPOSE 8000

CMD ["uvicorn", "marketpulse.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

