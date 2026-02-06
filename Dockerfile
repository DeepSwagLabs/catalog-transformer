FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY catalog_transformer.py .

ENV FLASK_APP=catalog_transformer.py

# Railway sets PORT env var dynamically
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} "catalog_transformer:create_app()"
