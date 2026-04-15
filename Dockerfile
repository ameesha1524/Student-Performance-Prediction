# Use an official lightweight Python image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and keep stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code and your ML model
COPY . /app/

# The port is dynamically injected by cloud providers, this is just documentation
EXPOSE 8080

# Command to run the app using Gunicorn (Optimized for 512MB RAM limits)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 2 --timeout 120 app:app"]