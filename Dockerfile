# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + serve frontend
FROM python:3.12-slim

# Install OpenCV system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy calibration data
COPY calibration/ /app/calibration/

# Copy frontend build output to be served as static files
COPY --from=frontend-builder /app/frontend/dist /app/static

# Create data directory for SQLite and images
RUN mkdir -p /data/images

ENV PT_DATABASE_URL=sqlite:////data/plant_tracker.db
ENV PT_IMAGE_DIR=/data/images
ENV PT_PROJECT_ROOT=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
