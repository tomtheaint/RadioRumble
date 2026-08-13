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

# The admin password, the fixture list and the voided contacts. /data was
# already created and given to appuser above, but nothing ever pointed at it --
# RR_DATA_DIR is what connects the two, and the volume is what keeps it across
# a deploy. Without it the image replaces the directory on every update: the
# password would be forgotten, sending the next person through first-run setup,
# and an official's voided contacts would quietly come back.
#
# Both go *here*, after the useradd, rather than up with the other ENV. They
# are metadata-only layers and cost nothing to rebuild, but anything above
# invalidates every layer below it -- putting RR_DATA_DIR in the ENV block at
# the top busted the useradd layer, which then took over two minutes to commit
# on the CI runner's disk and turned a 37-second build into one that looked
# hung. Cheap instructions belong last.
ENV RR_DATA_DIR=/data
VOLUME ["/data"]

WORKDIR /app
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 7373
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7373"]