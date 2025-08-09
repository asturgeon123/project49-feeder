FROM --platform=$BUILDPLATFORM python:3.12-slim-bookworm

# Install curl, then run the official uv installer script.
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/* && \
    curl -LsSf https://astral.sh/uv/install.sh | sh

# IMPORTANT: The installer places uv in /root/.local/bin.
# Add this directory to the PATH for all subsequent build steps and the final container.
ENV PATH="/root/.local/bin:${PATH}"

# Set the working directory inside the container
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Now that the correct uv is on the PATH, this command will work
RUN uv sync --locked

# Copy the rest of your code into the container
COPY main.py .

# The command that will be run when a container from this image is started
CMD ["uv", "run", "python", "main.py"]