FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# For HuggingFace Spaces: files are at root, package them as incident_env
COPY . /app/incident_env

# Install dependencies
RUN pip install --no-cache-dir \
    "openenv-core[core]>=0.2.2" \
    "fastapi>=0.100.0" \
    "uvicorn[standard]>=0.20.0" \
    "pydantic>=2.0.0" \
    "websockets>=11.0"

ENV PYTHONPATH="/app:$PYTHONPATH"

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "incident_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
