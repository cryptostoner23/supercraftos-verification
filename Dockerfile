# Override PYTHON_IMAGE with an approved digest for an immutable release build.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache

WORKDIR /app
COPY requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip check \
    && python -c "import tiktoken; tiktoken.get_encoding('o200k_base')" \
    && chmod -R a+rX /opt/tiktoken-cache \
    && groupadd --gid 10001 supercraftos \
    && useradd --uid 10001 --gid 10001 --create-home supercraftos \
    && chown 10001:10001 /app

# .dockerignore excludes runtime data, dotenv files and developer environments.
COPY --chown=10001:10001 . .
RUN mkdir -p /app/data && chown 10001:10001 /app/data && chmod 0700 /app/data

USER 10001:10001
STOPSIGNAL SIGINT
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import json, urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8787/api/status', timeout=3); assert json.load(r)['project']=='SuperCraftOS'"]

ENTRYPOINT ["python", "main.py"]
CMD ["app", "--host", "127.0.0.1", "--port", "8787"]
