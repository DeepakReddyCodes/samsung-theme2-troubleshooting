# Stage 1: Build React/Vite Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY deeplinks.json .
COPY siis_responses.json .
COPY schema.py .
COPY sample_output.json .

# Copy compiled production assets from builder
COPY --from=frontend-builder /build/dist frontend/dist

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
