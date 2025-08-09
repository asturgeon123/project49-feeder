# Use an official Python base image that supports arm/v7
FROM --platform=$BUILDPLATFORM python:3.12-slim-bookworm

# Install uv using pip
RUN pip install uv

# Set the working directory inside the container
WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .
# Use the uv installed via pip
RUN uv sync --locked

# Copy the rest of your code into the container
COPY main.py .

# The command that will be run when a container from this image is started
CMD ["uv", "run", "python", "main.py"]