FROM python:3.13-alpine AS builder

WORKDIR /app

COPY pyproject.toml poetry.lock ./

ENV POETRY_VERSION=2.1.3
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

RUN python -m poetry config virtualenvs.create true \
    && python -m poetry config virtualenvs.in-project true \
    && python -m poetry install --only main --no-interaction --no-ansi --no-root



FROM python:3.13-alpine

RUN apk add --no-cache curl \
    && rm -rf /var/cache/apk/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY ./manytask/ /app/manytask
COPY VERSION /app/VERSION
COPY .manytask.example.yml /app/.manytask.example.yml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CACHE_DIR=/cache

VOLUME ["/cache"]

EXPOSE 5050
HEALTHCHECK --interval=1m --timeout=15s --retries=3 --start-period=30s CMD curl -f http://localhost:5050/healthcheck
CMD ["gunicorn", "--bind", "0.0.0.0:5050", \
    "--access-logfile", "-", \
    "--log-file", "-", \
    "--capture-output", \
    "--workers", "2", \
    "--threads", "4", \
    "manytask:create_app()"]

# Set up Yandex.Cloud certificate
RUN mkdir -p /root/.postgresql && \
wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" \
    --output-document /root/.postgresql/root.crt && \
chmod 0600 /root/.postgresql/root.crt