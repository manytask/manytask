FROM python:3.14-alpine AS app_builder

WORKDIR /app

COPY pyproject.toml uv.lock VERSION ./
COPY ./manytask/ /app/manytask
COPY ./checker/pyproject.toml /app/checker/pyproject.toml

ENV UV_VERSION=0.11.8
RUN pip install uv==${UV_VERSION}

RUN apk add --no-cache build-base

RUN uv sync --locked --no-install-project


FROM python:3.14-alpine AS app

RUN apk add --no-cache curl \
    && rm -rf /var/cache/apk/*

WORKDIR /app

COPY --from=app_builder /app/.venv /app/.venv

COPY ./manytask/ /app/manytask
COPY VERSION /app/VERSION

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
    curl -o /root/.postgresql/root.crt https://storage.yandexcloud.net/cloud-certs/CA.pem \
        --retry 3 --retry-delay 2 --connect-timeout 10 && \
    chmod 0600 /root/.postgresql/root.crt

