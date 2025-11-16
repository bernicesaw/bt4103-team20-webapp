# Use lightweight Python image
FROM python:3.12-slim

# Avoid writing .pyc files & enable real-time logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory INSIDE the container
WORKDIR /app

# Install system dependencies needed by Django + your packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . /app/

# Expose Django’s default port
EXPOSE 8000

# Move into the myapp folder where manage.py lives
WORKDIR /app/myapp

# Run Django server for production-like environment
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
