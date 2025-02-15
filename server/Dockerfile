# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any are needed, e.g., for Pillow or other C-extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
# The 'app' directory from the build context (server/app) is copied to /app/app/ in the container.
# This means server/app/main.py will be available as /app/app/main.py.
COPY ./app /app/app/

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application
# Adjust the path to main:app if your FastAPI app instance is located elsewhere
# For example, if your app instance is in server/app/main.py, it would be app.main:app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
