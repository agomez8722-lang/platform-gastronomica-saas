FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt.
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/.
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
