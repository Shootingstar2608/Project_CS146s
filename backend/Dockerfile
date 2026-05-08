FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
# Note: We need to copy the entire project structure because 
# the backend depends on agent/ and pipeline/
COPY . .

# Set PYTHONPATH to include the root directory
ENV PYTHONPATH=/app

EXPOSE 8000

# Default command (can be overridden by docker-compose)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
