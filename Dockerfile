FROM python:3.12-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

EXPOSE 5000

# Use gunicorn with eventlet worker for Flask-SocketIO compatibility
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "app:app", "-b", "0.0.0.0:5000"]
