FROM python:3.12-slim

WORKDIR /app

COPY ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ui/ ui/

EXPOSE 8501

# headless = don't try to open a browser or ask for an email inside the container
CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
