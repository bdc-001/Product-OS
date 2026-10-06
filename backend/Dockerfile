# Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/srv/data

# git mirrors repositories; ffmpeg prepares voice clips and checks rendered video.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ /srv/backend/
COPY kits/ /srv/kits/
COPY render/ /srv/render/

RUN useradd --create-home --uid 1000 app && mkdir -p /srv/data && chown -R app:app /srv/data
USER app
VOLUME ["/srv/data"]
EXPOSE 8000

CMD ["sh", "-c", "python -m app migrate && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
