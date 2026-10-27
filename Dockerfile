# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
# Search's existing production client uses the eval-gemini dependency group.
# Editable install keeps the existing migration runner's /app/migrations lookup.
RUN uv sync --locked --no-dev --extra eval-gemini

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 daesingo \
    && useradd --uid 10001 --gid 10001 --no-create-home daesingo \
    && install -d -o 10001 -g 10001 -m 0750 /media /media/api-temp /media/worker-temp
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY migrations ./migrations
COPY docker/runtime.py ./docker/runtime.py
ARG REVISION=local
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DAESINGO_REVISION=$REVISION
USER 10001:10001
CMD ["python", "/app/docker/runtime.py", "api"]
