# Debian snapshot matches the dated inputs recorded by this immutable base.
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS base
RUN sed -i \
    -e 's@http://deb.debian.org/debian-security@https://snapshot.debian.org/archive/debian-security/20261027T000000Z@' \
    -e 's@http://deb.debian.org/debian@https://snapshot.debian.org/archive/debian/20261027T000000Z@' \
    /etc/apt/sources.list.d/debian.sources

FROM base AS media-build
RUN apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends build-essential pkg-config nasm curl xz-utils \
        libx264-dev zlib1g-dev libfreetype6-dev libharfbuzz-dev libfontconfig1-dev libfribidi-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
# Official release tarball; PGP verified before pinning (see Issue #465 Notes).
# No floating release URL, version range, or independently sourced probe binary.
RUN curl --fail --location --retry 3 --output ffmpeg.tar.xz https://ffmpeg.org/releases/ffmpeg-8.1.tar.xz \
    && echo 'b072aed6871998cce9b36e7774033105ca29e33632be5b6347f3206898e0756a  ffmpeg.tar.xz' | sha256sum -c - \
    && tar -xJf ffmpeg.tar.xz --strip-components=1 \
    && test "$(cat RELEASE)" = '8.1' \
    && ./configure --prefix=/opt/media --disable-autodetect --disable-doc --disable-debug --disable-ffplay \
        --enable-gpl --enable-libx264 --enable-zlib --enable-libfreetype --enable-libharfbuzz \
        --enable-libfontconfig --enable-libfribidi \
    && make -j4 \
    && make install \
    && mkdir -p /opt/media/identity \
    && python -c 'import hashlib,json,pathlib; p=pathlib.Path("/opt/media"); (p/"identity/media.json").write_text(json.dumps({"version":"8.1","sha256":{n:hashlib.sha256((p/"bin"/n).read_bytes()).hexdigest() for n in ("ffmpeg","ffprobe")}}))'

FROM base AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.15@sha256:e590846f4776907b254ac0f44b5b380347af5d90d668138ca7938d1b0c2f98d3 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
# Search's existing production client uses the eval-gemini dependency group.
# Editable install keeps the existing migration runner's /app/migrations lookup.
RUN uv sync --locked --no-dev --extra eval-gemini --extra readout-paddle

FROM build AS readout-build
RUN apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
ENV PADDLE_PDX_CACHE_HOME=/opt/daesingo/paddlex PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
COPY docker/readout_cache.py /build/readout_cache.py
RUN /app/.venv/bin/python /build/readout_cache.py

FROM base AS runtime
RUN apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends libx264-164 zlib1g \
        libfreetype6 libharfbuzz0b libfontconfig1 libfribidi0 fonts-dejavu-core \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 daesingo \
    && useradd --uid 10001 --gid 10001 --no-create-home daesingo \
    && install -d -o 10001 -g 10001 -m 0750 /media /media/api-temp /media/worker-temp
WORKDIR /app
COPY --from=media-build /opt/media/bin/ /usr/local/bin/
COPY --from=media-build /opt/media/identity/media.json /usr/local/share/daesingo/media.json
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=readout-build /opt/readout-cache /opt/daesingo/paddlex
RUN find /opt/daesingo/paddlex -type d -exec chmod 0555 {} + \
    && find /opt/daesingo/paddlex -type f -exec chmod 0444 {} + \
    && chown 10001:10001 /opt/daesingo/paddlex \
    && chmod 0750 /opt/daesingo/paddlex
COPY migrations ./migrations
COPY docker/runtime.py ./docker/runtime.py
ARG REVISION=local
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DAESINGO_REVISION=$REVISION
ENV PADDLE_PDX_CACHE_HOME=/opt/daesingo/paddlex PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
USER 10001:10001
RUN python /app/docker/runtime.py media-preflight
RUN --network=none python /app/docker/runtime.py readout-preflight
CMD ["python", "/app/docker/runtime.py", "api"]
