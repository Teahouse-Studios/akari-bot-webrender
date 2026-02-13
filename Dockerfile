FROM python:3.14

LABEL org.opencontainers.image.url=https://github.com/Teahouse-Studios/akari-bot-webrender
LABEL org.opencontainers.image.documentation=https://bot.teahouse.team/
LABEL org.opencontainers.image.source=https://github.com/Teahouse-Studios/akari-bot-webrender
LABEL org.opencontainers.image.vendor="Teahouse Studios"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.title="AkariBot WebRender"
LABEL maintainer="Teahouse Studios <admin@teahou.se>"

WORKDIR /akari-bot-webrender
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-dejavu \
    curl \
    wget \
    gnupg \
    ca-certificates \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

ADD . .
CMD ["python", "./run_server.py"]
