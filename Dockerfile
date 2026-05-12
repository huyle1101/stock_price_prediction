FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source code only — data/ and models/ are bind-mounted from host at runtime
COPY src/ ./src/

RUN mkdir -p /app/logs

CMD ["python", "-m", "src.pipeline.main"]
