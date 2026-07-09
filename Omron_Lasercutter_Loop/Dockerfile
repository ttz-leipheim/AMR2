# --- Build stage: install deps into a venv-like prefix ---
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.11-slim

# Non-root user for running the robot control process
RUN useradd --create-home --uid 1000 robot

WORKDIR /app

# Bring in the installed packages from the builder stage
COPY --from=builder /install /usr/local

# Application code
COPY main.py .
COPY README.md .
COPY src/ ./src/
COPY docs/ ./docs/
COPY installation/ ./installation/

# Config is meant to be mounted/overridden at runtime with your REAL
# robot_config.yaml (which contains live credentials and is never baked
# into the image - see .dockerignore). We ship the sanitized example
# under the real filename so the app has something to start with.
COPY config/robot_config.example.yaml ./config/robot_config.yaml

# logs/ is intentionally NOT copied in - it's created empty and meant to be
# mounted as a volume at runtime so logs survive container restarts.
RUN mkdir -p /app/logs && chown -R robot:robot /app

USER robot

# Unbuffered stdout so `docker logs` shows output live
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "main.py"]
