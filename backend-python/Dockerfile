# Backend Python (FastAPI) — SIH 26189
# Target architecture per ADR-001

FROM python:3.12-slim

WORKDIR /app

# System dependencies for potential native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Data directory (mounted at runtime)
RUN mkdir -p /app/data/synthetic

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]