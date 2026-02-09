# Karate Worker Dockerfile
# Runs Karate tests and reports results via Redis

FROM eclipse-temurin:17-jdk-jammy

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r karate && useradd -r -g karate karate

# Download Karate standalone JAR
ENV KARATE_VERSION=1.4.1
RUN mkdir -p /opt && \
    curl -L -o /opt/karate.jar \
    https://github.com/karatelabs/karate/releases/download/v${KARATE_VERSION}/karate-${KARATE_VERSION}.jar && \
    chmod 644 /opt/karate.jar

# Set up Python virtual environment
WORKDIR /app
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker script
COPY worker.py .

# Create workspace directory for test execution
RUN mkdir -p /workspace && chown -R karate:karate /workspace /app

# Switch to non-root user
USER karate

# Environment variables (can be overridden)
ENV REDIS_URL=redis://redis:6379
ENV LOG_LEVEL=INFO
ENV POLL_TIMEOUT=30
ENV JOB_TIMEOUT=300

WORKDIR /workspace

CMD ["python", "/app/worker.py"]
