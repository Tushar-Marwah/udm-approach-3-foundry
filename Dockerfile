# AmploFly4.0 — Unified Data Model demo (Flask + SQLite, single process)
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data/uploads /app/data/incoming

# bind to all interfaces; cloud platforms inject PORT
ENV HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

WORKDIR /app/backend
CMD ["python", "app.py"]
