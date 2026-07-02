# ---- Builder stage ----
FROM python:3.11-slim-bullseye AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Build deps needed to compile mysqlclient, Pillow, cryptography, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    default-libmysqlclient-dev \
    pkg-config \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --default-timeout=300 --retries 15

# ---- Runtime stage ----
FROM python:3.11-slim-bullseye AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Runtime shared libs that the compiled packages link against.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    libjpeg62-turbo \
    libfreetype6 \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 surfzone_logic.wsgi:application"]
