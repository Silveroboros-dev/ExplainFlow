# Use a slim Python base image for efficiency
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory within the container
WORKDIR /app

# Install system-level dependencies for gTTS and asset processing (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements first to leverage Docker layer caching
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code and schemas
COPY api/ /app/api/
COPY schemas/ /app/schemas/

# Create the assets directory for ephemeral storage (Cloud Run best practice)
RUN mkdir -p /app/api/app/static/assets

# Set PYTHONPATH to include both the root and the api directory
# This allows 'from app.routes' and other local imports to resolve
ENV PYTHONPATH=/app/api:/app

# Expose the port the FastAPI app will run on
EXPOSE 8080

# Change working directory to /app/api so relative paths in main.py work
WORKDIR /app/api

# Command to run the production server (Uvicorn)
# Note the app location is now 'app.main:app' because we are in /app/api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
