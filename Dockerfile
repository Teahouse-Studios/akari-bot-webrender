FROM mcr.microsoft.com/playwright/python:1.42.0-focal

LABEL org.opencontainers.image.url=https://github.com/Teahouse-Studios/akari-bot-webrender
LABEL org.opencontainers.image.documentation=https://bot.teahouse.team/
LABEL org.opencontainers.image.source=https://github.com/Teahouse-Studios/akari-bot-webrender
LABEL org.opencontainers.image.vendor="Teahouse Studios"
LABEL org.opencontainers.image.licenses=MIT
LABEL org.opencontainers.image.title="AkariBot WebRender"
MAINTAINER Teahouse Studios <admin@teahou.se>

WORKDIR /akari-bot-webrender
ADD . .

RUN apt-get update && apt-get install -y \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt --no-deps
CMD ["python", "./run_server.py"]
