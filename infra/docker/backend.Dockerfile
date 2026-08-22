FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY apps/backend/requirements.txt /workspace/apps/backend/requirements.txt
RUN pip install --no-cache-dir -r /workspace/apps/backend/requirements.txt

# Copy source code
COPY apps/backend /workspace/apps/backend

ENV PYTHONPATH=/workspace/apps/backend
WORKDIR /workspace/apps/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
