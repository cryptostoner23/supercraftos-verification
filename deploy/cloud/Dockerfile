# SuperCraftOS backend — portable container for any free cloud host.
# Runs the unified backend (dashboard server) on 0.0.0.0:8787.
# The private gateway (auth) is wrapped in the same image for public exposure.
FROM python:3.12-slim

WORKDIR /app

# System deps needed by some pinned wheels (cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

# Health/gateway entrypoint
ENV SUPERCRAFTOS_EMBEDDED_WORKER=0
ENV SUPERCRAFTOS_BACKEND_PORT=8787
ENV SUPERCRAFTOS_GATEWAY_PORT=8790
ENV SUPERCRAFTOS_PUBLIC_ORIGIN=https://scos.example.com

EXPOSE 8787 8790

# Start the private gateway (auth) which forwards to the backend.
CMD ["python", "private_gateway.py"]
