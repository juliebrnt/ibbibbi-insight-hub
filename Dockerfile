# Insight Hub: one container serves the API and the built web app.
# Build:  docker build -t insight-hub .
# Run:    docker run -p 8000:8000 -v insight-data:/data -e APP_PASSWORD=change-me insight-hub

FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY shared/ /app/shared/
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY shared/ shared/
COPY scripts/ scripts/
COPY demo_data/ demo_data/
COPY --from=web /app/frontend/dist frontend/dist
RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
