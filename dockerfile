


# Use a slim, official Python base image
FROM --platform=$BUILDPLATFORM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set the working directory inside the container
WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --locked

# Copy the rest of your code into the container
COPY main.py .

# The command that will be run when a container from this image is started
CMD ["uv", "run", "python", "main.py"]


