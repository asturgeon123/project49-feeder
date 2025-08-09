# Use a slim, official Python base image
FROM python:3.12-slim-bookworm

# Set the working directory inside the container
WORKDIR /app

# Copy the pyproject.toml file to the working directory
COPY pyproject.toml .

# Upgrade pip and install dependencies from pyproject.toml
RUN pip install --upgrade pip && pip install .

# Copy the rest of your code into the container
COPY main.py .

# The command that will be run when a container from this image is started
CMD ["python", "main.py"]