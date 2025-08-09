# Use an official Python base image that supports multi-arch builds
FROM --platform=$BUILDPLATFORM python:3.12-slim-bookworm

# Install curl, then run the official uv installer script.
# This is the most reliable way to get the correct binary for each architecture.
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/* && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

# Add the installation location of uv to the system's PATH environment variable
ENV PATH="/root/.cargo/bin:$PATH"

# Set the working directory inside the container
WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .

# Now that the correct uv is on the PATH, this command will work
RUN uv sync --locked

# Copy the rest of your code into the container
COPY main.py .

# The command that will be run when a container from this image is started
CMD ["uv", "run", "python", "main.py"]