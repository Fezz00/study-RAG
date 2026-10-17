FROM python:3.12-slim

WORKDIR /app

# Install dependencies first: this layer is cached and only rebuilt
# when requirements.txt changes, not on every code change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 8000

# 0.0.0.0 = accept connections from outside the container (127.0.0.1 would only allow the container itself)
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
