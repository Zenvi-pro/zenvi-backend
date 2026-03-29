FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    build-essential \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-manim.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-manim.txt

ARG CACHE_BUST=1
COPY . .

EXPOSE 8500

CMD ["python", "__main__.py"]
