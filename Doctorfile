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

# Expose port 8080 (Google Cloud Run's default)
EXPOSE 8080

# Command to run the app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "app:app"]