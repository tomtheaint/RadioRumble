FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

RUN useradd -u 1000 appuser && mkdir -p /data && chown appuser:appuser /data

WORKDIR /app
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 7373
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7373"]