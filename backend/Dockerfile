FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Add memory limit environment variables
ENV MALLOC_ARENA_MAX=2
ENV PYTHONMALLOC=malloc
ENV PYTHONPATH=/app
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5.00/tessdata
ENV DOCKER_CONTAINER=true

WORKDIR /app

# Install system dependencies without specific versions
RUN apt-get update && apt-get install -y \
    gcc \
    libpoppler-cpp-dev \
    pkgconf \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

# Use gunicorn for production
CMD gunicorn main:app --workers ${WORKERS:-4} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 75 \
    --keep-alive 120 \
    --max-requests 2000 \
    --max-requests-jitter 100 \
    --worker-tmp-dir /dev/shm \
    --preload
