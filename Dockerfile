# Use the official Python slim image for a smaller footprint
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PICOAGENT_ENV=docker

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging files
COPY pyproject.toml README.md ./

# Copy the actual package code
COPY picoagent/ ./picoagent/

# Install the package securely without editable mode since it's inside a container
RUN pip install --no-cache-dir .

# Create the standard .picoagent directory which users might mount
RUN mkdir -p /root/.picoagent

# Add a volume mount point so users can persist their memory/config
VOLUME ["/root/.picoagent"]

# By default, run the gateway with the default config path
ENTRYPOINT ["picoagent"]
CMD ["gateway", "--config", "/root/.picoagent/config.json"]
