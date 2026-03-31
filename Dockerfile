FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        fonts-liberation \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /tmp/video_service

EXPOSE 5000

CMD ["gunicorn", "--workers", "1", "--timeout", "300", "--bind", "0.0.0.0:5000", "--log-level", "info", "app:app"]
