# Backend image. Build from the repository root:  docker compose build backend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BI_DB_PATH=/data/bi_warehouse.duckdb
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# The app reads the repository root for the tracks' "open this file" feature, so these folders sit beside backend/.
COPY backend backend
COPY docs docs
COPY scripts scripts
COPY data_samples data_samples
RUN useradd --create-home --uid 10001 bi && mkdir -p /data && chown -R bi /data /app
USER bi
WORKDIR /app/backend
EXPOSE 8020
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8020/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]
