FROM python:3.11-slim

LABEL maintainer="LLM Regression Pipeline"
LABEL description="Production pipeline for LLM regression detection and reporting"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Default: run the full pipeline
CMD ["python", "run_full_pipeline.py"]
