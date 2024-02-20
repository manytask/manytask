FROM python:3.12-alpine as builder

RUN apk update && apk add --no-cache \
    build-base \
    linux-headers \
    libffi-dev \
    cargo \
    rust \
    && rm -rf /var/cache/apk/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt


FROM python:3.12-alpine

RUN apk update && apk add --no-cache \
    curl \
    && rm -rf /var/cache/apk/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

COPY ./manytask/ /app/manytask
COPY VERSION /app/VERSION

ENV CACHE_DIR=/cache SOLUTIONS_DIR=/solutions PYTHONPATH="${PYTHONPATH}:/app:/app/manytask"
VOLUME ["/cache", "/solutions"]

EXPOSE 5050
HEALTHCHECK --interval=1m --timeout=15s --retries=3 --start-period=30s CMD curl -f http://localhost:5050/healthcheck
CMD [
    "python",
    "-m",
    "gunicorn",
    "--bind",
    "0.0.0.0:5050",
    "--workers",
    "2",
    "--threads",
    "4",
    "manytask:create_app()"
]
#CMD python -m gunicorn \
#    --bind 0.0.0.0:5050 \
#    --workers 2 \
#    --threads 4 \
#    "manytask:create_app()"
#    --worker-class gthread \
#    --access-logfile - \
#    --access-logformat "%(t)s %({Host}i)s %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\" %(L)s %(b)s \"%(U)s\" \"%(q)s\"" \
#    --error-logfile -
