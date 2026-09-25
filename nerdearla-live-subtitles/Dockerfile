FROM python:3.11-slim

# ffmpeg para el script de prueba con archivos de audio
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
ENV HOST=0.0.0.0 PORT=8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
