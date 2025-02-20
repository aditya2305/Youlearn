FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Add memory limit environment variables
ENV MALLOC_ARENA_MAX=2
ENV PYTHONMALLOC=malloc

WORKDIR /app

RUN apt-get update && apt-get update && apt-get install -y \
    gcc \
    libpoppler-cpp-dev \
    pkg-config \
    poppler-utils \
    tesseract-ocr \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

# Use environment variable for workers
CMD uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-4} --timeout-keep-alive 75
