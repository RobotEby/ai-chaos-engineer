FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 && rm -rf /var/lib/apt/lists/*
COPY app.py /app.py
CMD ["python", "-u", "/app.py"]
