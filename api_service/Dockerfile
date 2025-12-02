FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static
COPY templates ./templates

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:api_application", "--host", "0.0.0.0", "--port", "8000"]

