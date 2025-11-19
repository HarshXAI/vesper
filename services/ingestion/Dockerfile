# Multi-stage build for VESPER Ingestion Service
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production image
FROM python:3.11-slim

# Install runtime dependencies including Docker CLI
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and add to docker group
# Note: Group ID 999 is typically the docker group in the host
RUN groupadd -g 999 docker || true && \
    useradd -m -u 1000 -G docker vesper && \
    mkdir -p /app && \
    chown -R vesper:vesper /app

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder to system
COPY --from=builder /root/.local /usr/local

# Copy application code
COPY . .

# Install the package
# Note: Running as root to allow docker socket access
RUN pip install -e .

# Add local bin to PATH
ENV PATH=/usr/local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from vesper_ingestion.config import get_config; get_config()" || exit 1

# Default command
ENTRYPOINT ["vesper-ingest"]
CMD ["--help"]
