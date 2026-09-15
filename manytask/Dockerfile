FROM python:3.14-alpine AS app_builder

WORKDIR /app

ENV UV_VERSION=0.11.8
RUN apk add --no-cache build-base \
    && pip install uv==${UV_VERSION}

# Build context: repository root (parent of manytask/), see docker-compose *.yml
# Only dependency manifests go here: app sources are copied in the final stage,
# so code changes do not invalidate the dependency layer.
COPY manytask/pyproject.toml manytask/uv.lock manytask/VERSION ./

RUN uv sync --locked --no-install-project


FROM python:3.14-alpine AS app

RUN apk add --no-cache curl \
    && rm -rf /var/cache/apk/*

# Set up Yandex.Cloud certificate
RUN mkdir -p /root/.postgresql && \
    curl -o /root/.postgresql/root.crt https://storage.yandexcloud.net/cloud-certs/CA.pem \
        --retry 3 --retry-delay 2 --connect-timeout 10 && \
    chmod 0600 /root/.postgresql/root.crt

WORKDIR /app

COPY --from=app_builder /app/.venv /app/.venv

COPY manytask/manytask/ /app/manytask
COPY manytask/VERSION /app/VERSION

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
