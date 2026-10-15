FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY migrations ./migrations
RUN uv sync --locked --no-dev --extra eval-gemini \
    && mkdir -p /srv/daesingo/media /srv/daesingo/api-temp /srv/daesingo/worker-temp \
    && chown -R 10001:10001 /srv/daesingo

USER 10001:10001
CMD ["python", "-m", "daesingo.worker"]
