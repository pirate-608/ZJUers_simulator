#
# ZJUers Simulator backend runtime image.
#
FROM python:3.11-slim-bookworm

WORKDIR /app

# PostgreSQL client headers are needed by database dependencies at install time.
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
