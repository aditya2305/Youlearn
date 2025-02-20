FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Add memory limit environment variables
ENV MALLOC_ARENA_MAX=2
ENV PYTHONMALLOC=malloc
ENV PYTHONPATH=/app
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
ENV DOCKER_CONTAINER=true

WORKDIR /app

# Install system dependencies in one layer with specific versions
RUN apt-get update && apt-get install -y \
    gcc=4:10.2.1-1 \
    libpoppler-cpp-dev=20.09.0-3.1 \
    pkg-config=0.29.2-1 \
    poppler-utils=20.09.0-3.1 \
    tesseract-ocr=4.1.1-2.1 \
    tesseract-ocr-eng=1:4.00~git30-7274cfa-1.1 \
    libtesseract-dev=4.1.1-2.1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

# Use gunicorn for production
CMD gunicorn main:app --workers ${WORKERS:-2} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --keep-alive 75 \
    --max-requests 1000 \
    --max-requests-jitter 50
