FROM python:3.12-slim-bookworm AS app-base

LABEL org.opencontainers.image.url=https://github.com/Teahouse-Studios/akari-bot-webrender
LABEL org.opencontainers.image.documentation=https://bot.teahouse.team/
LABEL org.opencontainers.image.source=https://github.com/Teahouse-Studios/akari-bot-webrender
LABEL org.opencontainers.image.vendor="Teahouse Studios"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.title="AkariBot WebRender"
LABEL maintainer="Teahouse Studios <admin@teahou.se>"

ARG WEBRENDER_UID=10001
ARG WEBRENDER_GID=10001
ARG UV_VERSION=0.10.3

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/webrender \
    PATH=/akari-bot-webrender/.venv/bin:${PATH} \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    WEBRENDER_HOST=0.0.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        fonts-dejavu \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "${WEBRENDER_GID}" webrender \
    && useradd --uid "${WEBRENDER_UID}" --gid "${WEBRENDER_GID}" --create-home --shell /bin/sh webrender \
    && install -d -o webrender -g webrender /akari-bot-webrender \
    && install -d -o root -g root -m 0755 /ms-playwright

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /akari-bot-webrender

COPY --chown=webrender:webrender pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project \
    && playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 15551

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import json, os, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:' + os.getenv('WEBRENDER_PORT', '15551') + '/status/', timeout=3); assert json.load(response).get('browser_initialized') is True"]

# The normal image remains headless. Build it explicitly with --target headless,
# or omit --target (the final default stage below is an alias of this stage).
FROM app-base AS headless

RUN playwright install --only-shell chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /home/webrender/.cache/ms-playwright

COPY --chown=webrender:webrender . .
RUN uv sync --frozen --no-dev \
    && chmod 0755 docker/entrypoint-headless.sh docker/entrypoint-gui.sh \
    && chown -R webrender:webrender /home/webrender

USER webrender
ENTRYPOINT ["/usr/bin/tini", "--", "./docker/entrypoint-headless.sh"]
CMD ["python", "./run_server.py"]


# Shared headed Chromium and virtual-X layer. Desktop targets add their own
# session implementation so the XFCE image does not also carry the lightweight WM.
FROM app-base AS headed-base

USER root
RUN playwright install --no-shell chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /home/webrender/.cache/ms-playwright \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        dbus-x11 \
        x11-utils \
        x11-xserver-utils \
        xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -m 1777 /tmp/.ICE-unix /tmp/.X11-unix

COPY --chown=webrender:webrender . .
RUN uv sync --frozen --no-dev \
    && chmod 0755 docker/entrypoint-headless.sh docker/entrypoint-gui.sh \
    && chown -R webrender:webrender /home/webrender

ENV DISPLAY=:99 \
    WEBRENDER_DEBUG=0 \
    WEBRENDER_HEADLESS=0 \
    XVFB_SCREEN=2560x1600x24

USER webrender
ENTRYPOINT ["/usr/bin/tini", "--", "./docker/entrypoint-gui.sh"]
CMD ["python", "./run_server.py"]


# Headed Chromium with a lightweight window manager.
FROM headed-base AS headed

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        twm \
        xfonts-base \
    && rm -rf /var/lib/apt/lists/*

ENV WEBRENDER_DESKTOP=twm

USER webrender


# Complete XFCE desktop with optional, password-protected noVNC access.
# noVNC is disabled unless ENABLE_NOVNC=1 is supplied at runtime.
FROM headed-base AS desktop

USER root
ARG NOVNC_VERSION=1.7.0
ARG NOVNC_SHA256=b1003a11b6e6e8d8f7f5e5586daae7f8ca651d8aee0aa155ff9ac841c48f52c6
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        xfce4 \
        x11vnc \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --frozen --no-dev --extra desktop \
    && python docker/install-novnc.py "${NOVNC_VERSION}" "${NOVNC_SHA256}" /usr/share/novnc

ENV ENABLE_NOVNC=0 \
    NO_AT_BRIDGE=1 \
    NOVNC_LISTEN=127.0.0.1 \
    NOVNC_PORT=6080 \
    VNC_PORT=5900 \
    WEBRENDER_DESKTOP=xfce

EXPOSE 6080

USER webrender


# Keep `docker build .` backward-compatible: the default artifact is headless.
FROM headless AS default
