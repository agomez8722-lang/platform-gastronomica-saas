FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install fastapi uvicorn pydantic python-multipart || pip install fastapi uvicorn pydantic
COPY . .
EXPOSE 8000
CMD ["python3","-m","uvicorn","app:app","--host","0.0.0.0","--port","8000","--reload"]
