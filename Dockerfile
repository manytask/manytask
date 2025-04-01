FROM python:3.13-alpine as builder

RUN apk update && apk add --no-cache \
    build-base \
    linux-headers \
    libffi-dev \
    cargo \
    rust \
    && rm -rf /var/cache/apk/*

# Install poetry
ENV POETRY_VERSION=1.7.1
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/opt/.cache

RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools \
    && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION}

ENV PATH="${PATH}:${POETRY_VENV}/bin"


FROM python:3.13-alpine

RUN apk update && apk add --no-cache \
    build-base \
    linux-headers \
    libffi-dev \
    cargo \
    rust \
    curl \
    && rm -rf /var/cache/apk/*

WORKDIR /app

COPY --from=builder /opt/poetry-venv /opt/poetry-venv
COPY pyproject.toml poetry.lock ./

ENV PATH="/opt/poetry-venv/bin:$PATH" PYTHONPATH="/app:/app/manytask"

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY ./manytask/ /app/manytask
COPY VERSION /app/VERSION

ENV CACHE_DIR=/cache SOLUTIONS_DIR=/solutions

VOLUME ["/cache", "/solutions"]

EXPOSE 5050
HEALTHCHECK --interval=1m --timeout=15s --retries=3 --start-period=30s CMD curl -f http://localhost:5050/healthcheck
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "2", "--threads", "4", "manytask:create_app()"]

# Set up Yandex.Cloud certificate
RUN mkdir -p /root/.postgresql && \
wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" \
    --output-document /root/.postgresql/root.crt && \
chmod 0600 /root/.postgresql/root.crt
